"""Live aircraft position fetcher — multi-source with automatic failover.

Uses 4 free ADS-B APIs (all share identical ADSBExchange v2 format):
1. airplanes.live — primary (1 req/sec limit, excellent docs)
2. adsb.lol — fallback (dynamic rate limits)
3. adsb.fi — fallback (1 req/sec, v3 geo endpoint)
4. adsb.one — fallback (1 req/sec)
5. OpenSky Network — last resort (global coverage, different format)

Strategy: Rotate through ADS-B sources for regional queries + dedicated
military endpoint. Merge with OpenSky for maximum coverage.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional

import httpx

from ..flight_intel import FlightIntelligence
from ..mil_hex_db import is_military_hex, enrich_from_hexdb, format_enrichment
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

# ADS-B API sources — two URL styles:
#   "point" = /v2/point/{lat}/{lon}/{dist}  (airplanes.live, adsb.one, adsb.lol)
#   "latlon" = /v2/lat/{lat}/lon/{lon}/dist/{dist}  (adsb.fi)
_ADSB_SOURCES = [
    ("airplanes.live", "https://api.airplanes.live", "point"),
    ("adsb.one", "https://api.adsb.one", "point"),
    ("adsb.fi", "https://opendata.adsb.fi/api", "latlon"),
    ("adsb.lol", "https://api.adsb.lol", "point"),
]

# Regional queries: (name, center_lat, center_lon, radius_nm)
# Max 250nm per request — batched 4 at a time across all ADS-B sources
_REGIONS = [
    # Americas
    ("NE.US", 41.0, -74.0, 250), ("SE.US", 33.0, -84.0, 250),
    ("W.US", 37.0, -122.0, 250), ("C.US", 39.0, -98.0, 250),
    ("S.US", 29.8, -95.4, 250), ("Canada", 43.7, -79.4, 250),
    ("Mexico", 19.4, -99.1, 250), ("Brazil", -23.5, -46.6, 250),
    ("Colombia", 4.6, -74.1, 250), ("Argentina", -34.6, -58.4, 250),
    ("Caribbean", 18.5, -72.0, 250),
    # Europe
    ("W.Eur", 48.5, 2.3, 250), ("C.Eur", 50.0, 14.0, 250),
    ("UK", 52.0, -1.0, 250), ("Scandi", 59.0, 18.0, 250),
    ("S.Eur", 41.0, 12.0, 250), ("Iberia", 40.4, -3.7, 250),
    ("Turkey", 41.0, 29.0, 250), ("E.Eur", 52.2, 21.0, 250),
    # Middle East & Central Asia
    ("MidEast", 25.3, 55.0, 250), ("E.Med", 33.0, 35.0, 250),
    ("Gulf", 29.0, 48.0, 250), ("Iran", 35.7, 51.4, 250),
    ("SaudiW", 21.5, 39.2, 250), ("CentralAsia", 41.3, 69.3, 250),
    # Asia-Pacific
    ("India", 19.0, 73.0, 250), ("Delhi", 28.6, 77.2, 250),
    ("China.E", 31.2, 121.4, 250), ("China.S", 23.1, 113.3, 250),
    ("Japan", 35.7, 139.7, 250), ("SEAsia", 1.3, 103.8, 250),
    ("Korea", 37.5, 127.0, 250), ("Thailand", 13.7, 100.5, 250),
    ("Philippines", 14.6, 121.0, 250),
    # Africa
    ("N.Africa", 33.6, -7.6, 250), ("Egypt", 30.0, 31.2, 250),
    ("W.Africa", 6.5, 3.4, 250), ("E.Africa", -1.3, 36.8, 250),
    ("S.Africa", -26.2, 28.0, 250),
    # Oceania
    ("Aus.E", -33.9, 151.2, 250), ("NZ", -36.8, 174.8, 250),
    # Gap coverage — underserved areas between primary circles
    ("Pacific", 20.0, -155.0, 250), ("Alaska", 61.0, -150.0, 250),
    ("N.Atlantic", 50.0, -30.0, 250), ("S.Atlantic", -10.0, -25.0, 250),
    ("IndOcean", -10.0, 55.0, 250), ("CentralAfr", 0.0, 20.0, 250),
    ("Pakistan", 24.9, 67.0, 250), ("Bangladesh", 23.8, 90.4, 250),
    ("Indonesia", -6.2, 106.8, 250), ("Peru", -12.0, -77.0, 250),
    ("Chile", -33.4, -70.6, 250), ("W.China", 39.5, 75.0, 250),
    ("Vietnam", 21.0, 105.8, 250), ("Myanmar", 16.8, 96.2, 250),
    ("Libya", 32.9, 13.2, 250), ("Iraq", 33.3, 44.4, 250),
]

_ADSB_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=30.0)
_OPENSKY_TIMEOUT = httpx.Timeout(connect=10.0, read=45.0, write=5.0, pool=10.0)


class FlightFetcher(BaseFetcher):
    """Multi-source aircraft position fetcher with automatic failover.

    Rotates through 4 free ADS-B APIs to maximize uptime and avoid rate limits.
    Falls back to OpenSky for global coverage if all ADS-B sources fail.
    """

    def __init__(self, intel: FlightIntelligence) -> None:
        self._intel = intel
        self._source_idx: int = 0
        self._last_success: Dict[str, float] = {}  # track which sources work
        self._mil_hex_codes: List[str] = []  # collect military hex for enrichment

    def _enrich_adsb(self, ac: dict, seen: set) -> Optional[dict]:
        """Parse a single ADS-B v2 aircraft dict into enriched flight.

        Args:
            ac: Raw aircraft dict from any ADS-B v2 API.
            seen: Set of already-processed ICAO24 hex IDs.

        Returns:
            Enriched flight dict, or None if invalid/duplicate.
        """
        hex_id = ac.get("hex", "").strip().lower()
        if not hex_id or hex_id in seen:
            return None
        lat, lon = ac.get("lat"), ac.get("lon")
        if lat is None or lon is None:
            return None
        alt = ac.get("alt_baro")
        on_ground = alt == "ground" or alt == 0
        if on_ground:
            alt = 0
        seen.add(hex_id)

        callsign = (ac.get("flight") or "").strip()
        db_flags = ac.get("dbFlags", 0)
        is_mil_db = FlightIntelligence.is_military_dbflags(db_flags)

        state_vec = [
            hex_id, callsign, ac.get("r", ""), None, None,
            lon, lat, alt if isinstance(alt, (int, float)) else None,
            on_ground, ac.get("gs"), ac.get("track"), ac.get("baro_rate"),
            None, ac.get("alt_geom"), ac.get("squawk"), ac.get("alert", False), 0,
        ]
        enriched = self._intel.enrich_flight(state_vec)
        if not enriched:
            return None

        # Only apply dbFlags military if callsign is NOT a known civilian airline
        if is_mil_db and not self._intel.is_civilian_airline(callsign):
            enriched["is_military"] = True

        # Check tar1090-db military hex ranges
        mil_hex_info = is_military_hex(hex_id)
        if mil_hex_info and not self._intel.is_civilian_airline(callsign):
            enriched["is_military"] = True
            enriched["mil_country"] = mil_hex_info[0]
            enriched["mil_branch"] = mil_hex_info[1]

        if ac.get("gs") is not None:
            enriched["velocity"] = ac["gs"]
        if ac.get("t"):
            enriched["aircraft_type"] = ac["t"]
        if ac.get("r"):
            enriched["registration"] = ac["r"]

        # Track military hex codes for batch enrichment
        if enriched.get("is_military"):
            self._mil_hex_codes.append(hex_id)

        return enriched

    def _parse_opensky(self, states: list, seen: set) -> List[dict]:
        """Parse OpenSky state vectors into enriched flight dicts.

        Args:
            states: Raw state vector list from OpenSky.
            seen: Set of already-processed ICAO24 hex IDs.

        Returns:
            List of enriched flight dicts.
        """
        results: List[dict] = []
        for s in (sv for sv in states if len(sv) >= 17):
            if s[0] in seen or s[6] is None or s[5] is None:
                continue
            seen.add(s[0])
            enriched = self._intel.enrich_flight(s)
            if enriched:
                results.append(enriched)
        return results

    @staticmethod
    def _build_url(base_url: str, style: str, lat: float, lon: float, dist: int) -> str:
        """Build the regional query URL based on source style.

        Args:
            base_url: API base URL.
            style: "point" or "latlon".
            lat, lon, dist: Query parameters.

        Returns:
            Full URL string.
        """
        if style == "latlon":
            return f"{base_url}/v2/lat/{lat}/lon/{lon}/dist/{dist}"
        return f"{base_url}/v2/point/{lat}/{lon}/{dist}"

    async def _fetch_one_region(
        self, client: httpx.AsyncClient, src_name: str, base_url: str,
        style: str, region_name: str, lat: float, lon: float, dist: int,
        seen: set, merged: Dict[str, dict],
    ) -> bool:
        """Fetch one region from one ADS-B source (no fallback — saves rate budget).

        No fallback retry: source rotation across cycles ensures each region
        gets a different source next time, so failures are transient.

        Args:
            client: httpx client.
            src_name: Source name for logging.
            base_url: Base URL for the ADS-B API.
            style: URL style ("point" or "latlon").
            region_name: Region name for logging.
            lat, lon, dist: Query parameters.
            seen: Set of already-processed ICAO24 hex IDs.
            merged: Dict to update with enriched flights.

        Returns:
            True if data was fetched successfully.
        """
        try:
            url = self._build_url(base_url, style, lat, lon, dist)
            resp = await client.get(url)
            if resp.status_code == 429:
                logger.debug("%s rate limited for %s", src_name, region_name)
                return False
            if resp.status_code != 200:
                return False
            data = resp.json()
            for ac in data.get("ac") or data.get("aircraft") or []:
                enriched = self._enrich_adsb(ac, seen)
                if enriched:
                    merged[enriched["icao24"]] = enriched
            self._last_success[src_name] = time.monotonic()
            return True
        except Exception as exc:
            logger.debug("%s %s: %s: %s", src_name, region_name, type(exc).__name__, exc)
            return False

    async def _fetch_adsb_regions(self) -> Dict[str, dict]:
        """Fetch aircraft from regional queries across ADS-B sources.

        Uses concurrent batching: queries all 4 ADS-B sources simultaneously,
        each with a different region. 4 regions per 1.1s cycle = ~16s for 57 regions.

        Returns:
            Dict mapping icao24 -> enriched flight dict.
        """
        merged: Dict[str, dict] = {}
        seen: set = set()
        num_sources = len(_ADSB_SOURCES)
        batch_size = num_sources

        async with httpx.AsyncClient(
            timeout=_ADSB_TIMEOUT,
            follow_redirects=True,
            http2=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
        ) as client:
            # Fetch military aircraft first (single call)
            await self._fetch_military(client, seen, merged)
            await asyncio.sleep(1.5)

            # Batch regions: 4 concurrent requests per cycle (one per ADS-B source)
            regions_fetched = 0
            batch_num = 0
            for batch_start in range(0, len(_REGIONS), batch_size):
                batch = _REGIONS[batch_start:batch_start + batch_size]
                tasks = []
                for j, (rname, lat, lon, dist) in enumerate(batch):
                    src_idx = (j + batch_num) % num_sources
                    src_name, base_url, style = _ADSB_SOURCES[src_idx]
                    tasks.append(
                        self._fetch_one_region(
                            client, src_name, base_url, style,
                            rname, lat, lon, dist, seen, merged,
                        )
                    )
                results = await asyncio.gather(*tasks, return_exceptions=True)
                regions_fetched += sum(1 for r in results if r is True)
                batch_num += 1
                await asyncio.sleep(1.1)

        logger.info("ADS-B sources: %d aircraft from %d/%d regions",
                     len(merged), regions_fetched, len(_REGIONS))
        return merged

    async def _fetch_military(self, client: httpx.AsyncClient, seen: set, merged: Dict[str, dict]) -> None:
        """Fetch all military-tagged aircraft via /v2/mil endpoint.

        Args:
            client: httpx client.
            seen: Set of seen ICAO24 hex IDs.
            merged: Dict to update with military aircraft.
        """
        for src_name, base_url, _style in _ADSB_SOURCES:
            try:
                resp = await client.get(f"{base_url}/v2/mil", timeout=15.0)
                if resp.status_code == 200:
                    data = resp.json()
                    ac_list = data.get("ac") or data.get("aircraft") or []
                    mil_count = 0
                    for ac in ac_list:
                        enriched = self._enrich_adsb(ac, seen)
                        if enriched:
                            enriched["is_military"] = True
                            merged[enriched["icao24"]] = enriched
                            mil_count += 1
                    logger.info("Military aircraft (%s): %d", src_name, mil_count)
                    self._last_success[src_name] = time.monotonic()
                    return
            except Exception as exc:
                logger.debug("Military fetch %s: %s", src_name, exc)
        logger.warning("All military endpoints failed")

    async def _fetch_by_type(self, seen: set, merged: Dict[str, dict]) -> None:
        """Fetch aircraft globally by aircraft type codes using 2 dedicated sources.

        Queries adsb.lol + adsb.one in parallel (2 type queries per 1.2s cycle).
        Covers 40+ aircraft types to catch flights in uncovered areas globally.

        Args:
            seen: Set of already-processed ICAO24 hex IDs.
            merged: Dict to update with enriched flights.
        """
        _COMMON_TYPES = [
            # Narrowbody (highest count)
            "B738", "A320", "A321", "A21N", "A20N", "B39M", "B737", "A319",
            "B38M", "B739", "E195", "E190", "CRJ9", "CRJ7", "E75L", "E75S",
            "AT76", "DH8D", "BCS3", "BCS1", "B712",
            # Widebody
            "B77W", "B789", "B788", "A332", "A333", "B772", "B763",
            "A359", "A35K", "A388", "B744", "B78X", "A339", "B764",
            # Regional / turboprop
            "E145", "AT75", "SF34", "C208", "PC12",
            # Cargo
            "B77L", "A306", "B752", "B753",
        ]
        # Two dedicated sources for type queries (batched 2 at a time)
        type_sources = [
            ("adsb.lol", "https://api.adsb.lol"),
            ("adsb.one", "https://api.adsb.one"),
        ]
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=8.0, read=20.0, write=5.0, pool=20.0),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
        ) as client:
            type_count = 0
            stopped = set()
            for batch_start in range(0, len(_COMMON_TYPES), len(type_sources)):
                batch = _COMMON_TYPES[batch_start:batch_start + len(type_sources)]
                tasks = []
                for j, aircraft_type in enumerate(batch):
                    src_name, base_url = type_sources[j % len(type_sources)]
                    if src_name in stopped:
                        continue
                    tasks.append(
                        self._fetch_type_single(
                            client, base_url, src_name, aircraft_type, seen, merged,
                        )
                    )
                if not tasks:
                    break
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, int):
                        type_count += r
                    elif isinstance(r, str):
                        stopped.add(r)
                await asyncio.sleep(1.2)
            logger.info("Type-based fetch: %d additional aircraft from %d types",
                        type_count, len(_COMMON_TYPES))

    async def _fetch_type_single(
        self, client: httpx.AsyncClient, base_url: str, src_name: str,
        aircraft_type: str, seen: set, merged: Dict[str, dict],
    ) -> int | str:
        """Fetch one aircraft type from one source.

        Returns:
            int: Number of new aircraft added, or
            str: Source name if rate-limited (signals to stop using that source).
        """
        try:
            resp = await client.get(f"{base_url}/v2/type/{aircraft_type}")
            if resp.status_code == 429:
                return src_name  # signal to stop this source
            if resp.status_code != 200:
                return 0
            data = resp.json()
            count = 0
            for ac in data.get("ac") or []:
                enriched = self._enrich_adsb(ac, seen)
                if enriched:
                    merged[enriched["icao24"]] = enriched
                    count += 1
            return count
        except Exception:
            return 0

    async def _fetch_opensky(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch global aircraft from OpenSky Network (single attempt, no retry spam).

        Args:
            client: Shared httpx client.

        Returns:
            List of enriched flight dicts.
        """
        try:
            resp = await client.get(
                "https://opensky-network.org/api/states/all",
                timeout=_OPENSKY_TIMEOUT,
            )
            if resp.status_code == 429:
                logger.debug("OpenSky rate limited, skipping")
                return []
            resp.raise_for_status()
            states = resp.json().get("states") or []
            results = self._parse_opensky(states, set())
            logger.info("OpenSky: %d aircraft (global)", len(results))
            return results
        except Exception as exc:
            logger.debug("OpenSky: %s", exc)
            return []

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch flights from all sources, merge, and deduplicate.

        Strategy:
        1. Fetch military aircraft from /v2/mil (single call)
        2. Batch 57 regions across 4 ADS-B sources concurrently (~16s)
        3. Fetch by aircraft type globally (catches flights in uncovered areas, ~18s)
        4. Try OpenSky once (often rate-limited, but free bonus when it works)
        5. All three run concurrently

        Args:
            client: Shared httpx client (used for OpenSky).

        Returns:
            List of enriched flight dicts.
        """
        # Shared state for all concurrent fetchers
        merged: Dict[str, dict] = {}
        seen: set = set()

        # Run regional + OpenSky concurrently, then type-based with shared state
        regional_task = asyncio.create_task(self._fetch_adsb_regions())
        opensky_task = asyncio.create_task(self._fetch_opensky(client))

        adsb_data = await regional_task
        opensky_flights = await opensky_task

        # Populate shared state from regional results so type-based can dedup
        for icao, flight in adsb_data.items():
            merged[icao] = flight
            seen.add(icao)

        # Now run type-based fetch with populated seen/merged
        await self._fetch_by_type(seen, merged)

        if not adsb_data and not opensky_flights and not merged:
            logger.warning("All flight sources failed")
            return []

        # Merge OpenSky: only add aircraft not already seen from ADS-B
        for flight in opensky_flights:
            icao = flight.get("icao24", "")
            if icao and icao not in merged:
                merged[icao] = flight

        overrides = 0
        for icao, flight in adsb_data.items():
            if icao in merged and merged[icao] is not flight:
                overrides += 1
            merged[icao] = flight

        results = list(merged.values())

        # Enrich military aircraft with hexdb.io owner/operator data
        mil_hexes = [f.get("icao24", "") for f in results if f.get("is_military")]
        if mil_hexes:
            try:
                enrichments = await enrich_from_hexdb(client, mil_hexes[:50])
                enriched_count = 0
                for flight in results:
                    hx = flight.get("icao24", "").lower()
                    if hx in enrichments and enrichments[hx]:
                        info = format_enrichment(enrichments[hx])
                        if info.get("owner"):
                            flight["owner"] = info["owner"]
                        if info.get("aircraft_model"):
                            flight["aircraft_model"] = info["aircraft_model"]
                        if info.get("manufacturer"):
                            flight["manufacturer"] = info["manufacturer"]
                        if info.get("registration") and not flight.get("registration"):
                            flight["registration"] = info["registration"]
                        enriched_count += 1
                logger.info("hexdb.io enriched %d/%d military aircraft", enriched_count, len(mil_hexes))
            except Exception as exc:
                logger.debug("hexdb.io enrichment failed: %s", exc)

        logger.info(
            "Flights merged: %d total (OpenSky=%d, ADS-B regional=%d, overrides=%d)",
            len(results), len(opensky_flights), len(adsb_data), overrides,
        )
        return results
