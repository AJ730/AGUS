"""Live aircraft position fetcher using adsb.lol and OpenSky."""

from __future__ import annotations

import asyncio
import logging
from typing import List

import httpx

from ..flight_intel import FlightIntelligence
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

FLIGHT_REGIONS = [  # (name, lamin, lomin, lamax, lomax)
    ("N.America", 24, -130, 55, -60), ("Europe", 35, -12, 72, 45),
    ("MidEast", 12, 25, 42, 65), ("E.Asia", 15, 90, 55, 150),
    ("S.Asia", 5, 60, 40, 98), ("Africa", -35, -20, 37, 52),
    ("S.America", -56, -82, 15, -34), ("Oceania", -50, 100, 0, 180),
]


class FlightFetcher(BaseFetcher):
    """Fetches live aircraft positions from adsb.lol with OpenSky fallback."""

    def __init__(self, intel: FlightIntelligence):
        self._intel = intel

    def _parse_adsb(self, aircraft: list, seen: set) -> List[dict]:
        results: List[dict] = []
        for ac in aircraft:
            hex_id = ac.get("hex", "").strip().lower()
            if not hex_id or hex_id in seen:
                continue
            lat, lon = ac.get("lat"), ac.get("lon")
            if lat is None or lon is None:
                continue
            alt = ac.get("alt_baro")
            if alt == "ground" or alt == 0:
                continue
            seen.add(hex_id)
            callsign = (ac.get("flight") or "").strip()
            db_flags = ac.get("dbFlags", 0)
            is_mil_db = bool(db_flags & 1) if isinstance(db_flags, int) else False
            state_vec = [
                hex_id, callsign, ac.get("r", ""), None, None,
                lon, lat, alt if isinstance(alt, (int, float)) else None,
                False, ac.get("gs"), ac.get("track"), ac.get("baro_rate"),
                None, ac.get("alt_geom"), ac.get("squawk"), ac.get("alert", False), 0,
            ]
            enriched = self._intel.enrich_flight(state_vec)
            if enriched:
                if is_mil_db:
                    enriched["is_military"] = True
                if ac.get("gs") is not None:
                    enriched["velocity"] = ac["gs"]
                if ac.get("t"):
                    enriched["aircraft_type"] = ac["t"]
                if ac.get("r"):
                    enriched["registration"] = ac["r"]
                results.append(enriched)
        return results

    def _parse_opensky(self, states: list, seen: set) -> List[dict]:
        results: List[dict] = []
        for s in (sv for sv in states if len(sv) >= 17):
            if s[0] in seen or s[6] is None or s[5] is None or s[8]:
                continue
            seen.add(s[0])
            enriched = self._intel.enrich_flight(s)
            if enriched:
                results.append(enriched)
        return results

    async def _from_adsb(self, client: httpx.AsyncClient) -> List[dict]:
        results, seen = [], set()
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)
        for name, lamin, lomin, lamax, lomax in FLIGHT_REGIONS:
            clat, clon = (lamin + lamax) / 2, (lomin + lomax) / 2
            dist_nm = int(max(lamax - lamin, lomax - lomin) * 30)
            try:
                resp = await client.get(
                    f"https://api.adsb.lol/v2/lat/{clat}/lon/{clon}/dist/{dist_nm}",
                    timeout=timeout,
                )
                resp.raise_for_status()
                ac_list = resp.json().get("ac") or resp.json().get("aircraft") or []
                results.extend(self._parse_adsb(ac_list, seen))
            except Exception as exc:
                logger.warning("adsb.lol %s: %s", name, exc)
            await asyncio.sleep(0.5)
        return results

    async def _from_opensky(self, client: httpx.AsyncClient) -> List[dict]:
        t = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)
        for attempt in range(2):
            try:
                resp = await client.get("https://opensky-network.org/api/states/all", timeout=t)
                if resp.status_code == 429:
                    await asyncio.sleep(12.0); continue
                resp.raise_for_status()
                return self._parse_opensky(resp.json().get("states") or [], set())
            except Exception as exc:
                logger.warning("OpenSky attempt %d: %s", attempt + 1, exc)
                await asyncio.sleep(12.0)
        return []

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(client, self._from_adsb, self._from_opensky)
