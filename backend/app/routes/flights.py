"""Flight-related endpoints: viewport fetch and per-aircraft detail."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..cache import CacheEntry
from ..mil_hex_db import is_military_hex
from ._helpers import _cache, _client, _fetcher_fns, _intel

logger = logging.getLogger("agus.routes")

router = APIRouter()

# Per-icao24 flight detail cache
_flight_detail_cache: Dict[str, CacheEntry] = {}
_flight_detail_locks: Dict[str, asyncio.Lock] = {}
_FLIGHT_DETAIL_TTL = 15.0


@router.get("/flights_viewport")
async def flights_viewport(request: Request, lat: float = 0, lon: float = 0, dist: int = 250):
    """On-demand flight fetch for the user's current map viewport.

    Queries ADS-B APIs for the specific region the user is looking at,
    merges with cached global flights, and returns the combined result.
    This ensures precise coverage where the user is actually looking.

    Args:
        lat: Viewport center latitude.
        lon: Viewport center longitude.
        dist: Radius in nautical miles (max 250).
    """
    from ..fetchers.flights import _ADSB_SOURCES, FlightFetcher

    dist = min(dist, 250)
    cache = _cache(request)
    intel = _intel(request)

    # Get cached global flights as base
    fns = _fetcher_fns(request)
    base_data = await cache.get("flights", fns["flights"])
    base_flights = base_data if isinstance(base_data, list) else []

    # Build index of existing icao24s
    existing = {f.get("icao24"): f for f in base_flights if f.get("icao24")}

    # Fetch viewport-specific flights from ADS-B sources
    fetcher = FlightFetcher(intel)
    new_count = 0
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=8.0, read=15.0, write=5.0, pool=10.0),
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        },
    ) as vp_client:
        seen: set = set(existing.keys())
        for src_name, base_url, style in _ADSB_SOURCES:
            try:
                url = FlightFetcher._build_url(base_url, style, lat, lon, dist)
                resp = await vp_client.get(url)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for ac in data.get("ac") or data.get("aircraft") or []:
                    enriched = fetcher._enrich_adsb(ac, seen)
                    if enriched and enriched["icao24"] not in existing:
                        existing[enriched["icao24"]] = enriched
                        new_count += 1
                break  # one success is enough
            except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError):
                continue

    result = list(existing.values())
    logger.info("Viewport fetch (%.1f,%.1f r=%dnm): +%d new, %d total",
                lat, lon, dist, new_count, len(result))
    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Flight detail (per-icao24 with track)
# ---------------------------------------------------------------------------

async def _fetch_flight_detail(client: httpx.AsyncClient, icao24: str, intel) -> dict:
    """Fetch detailed state + track for a single aircraft."""
    result: dict = {"icao24": icao24, "state": None, "track": []}

    # Primary: airplanes.live single-aircraft lookup
    try:
        resp = await client.get(
            f"https://api.airplanes.live/v2/hex/{icao24}",
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
        )
        resp.raise_for_status()
        data = resp.json()
        aircraft_list = data.get("ac") or []
        if aircraft_list:
            ac = aircraft_list[0]
            callsign = (ac.get("flight") or "").strip()
            squawk = ac.get("squawk")
            alt = ac.get("alt_baro")
            if alt == "ground":
                alt = 0
            result["state"] = {
                "icao24": icao24,
                "callsign": callsign,
                "origin_country": ac.get("r", ""),
                "longitude": ac.get("lon"),
                "latitude": ac.get("lat"),
                "baro_altitude": alt if isinstance(alt, (int, float)) else None,
                "on_ground": alt == 0 or alt == "ground",
                "velocity": ac.get("gs"),
                "heading": ac.get("track"),
                "vertical_rate": ac.get("baro_rate"),
                "geo_altitude": ac.get("alt_geom"),
                "squawk": squawk,
                "aircraft_type": ac.get("t", intel.estimate_aircraft_type(icao24)),
                "registration": ac.get("r", ""),
                "flight_route": intel.estimate_route(callsign),
                "is_military": (
                    intel.is_military(callsign, icao24)
                    or (intel.is_military_dbflags(ac.get("dbFlags", 0))
                        and not intel.is_civilian_airline(callsign))
                    or (bool(is_military_hex(icao24))
                        and not intel.is_civilian_airline(callsign))
                ),
                "squawk_alert": intel.detect_squawk_alert(squawk) if squawk else None,
            }
    except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
        logger.warning("adsb.lol detail fetch failed for %s: %s", icao24, exc)

    # Track/trace from airplanes.live (per-aircraft lookup)
    try:
        trace_resp = await client.get(
            f"https://api.airplanes.live/v2/hex/{icao24}",
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
        )
        trace_resp.raise_for_status()
        trace_data = trace_resp.json()
        trace_ac = (trace_data.get("ac") or [])
        if trace_ac:
            ac = trace_ac[0]
            lat = ac.get("lat")
            lon = ac.get("lon")
            alt = ac.get("alt_baro")
            if isinstance(alt, str):
                alt = 0
            if lat is not None and lon is not None:
                result["track"] = [{
                    "latitude": lat,
                    "longitude": lon,
                    "altitude": alt if isinstance(alt, (int, float)) else 10000,
                }]
    except httpx.HTTPError as exc:
        logger.warning("airplanes.live trace fetch failed for %s: %s", icao24, exc)

    # Fallback: OpenSky track (may 429, but try)
    if not result["track"]:
        try:
            track_resp = await client.get(
                f"https://opensky-network.org/api/tracks/all?icao24={icao24}&time=0",
                timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            )
            track_resp.raise_for_status()
            track_data = track_resp.json()
            path = track_data.get("path") or []
            waypoints = []
            for wp in path:
                if len(wp) >= 4:
                    waypoints.append({
                        "latitude": wp[1], "longitude": wp[2],
                        "altitude": wp[3],
                    })
            result["track"] = waypoints
        except (httpx.HTTPError, httpx.TimeoutException):
            pass  # OpenSky often 429s, silently fall through

    return result


@router.get("/flight_detail/{icao24}")
async def flight_detail(icao24: str, request: Request):
    """Fetch detailed state and track for a single aircraft by ICAO24 hex."""
    icao24 = icao24.lower().strip()
    if not icao24 or len(icao24) != 6:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid ICAO24 address. Must be a 6-character hex string."},
        )

    client = _client(request)
    intel = _intel(request)

    # Check cache freshness
    entry = _flight_detail_cache.get(icao24)
    if entry and entry.data is not None and (time.monotonic() - entry.fetched_at) < _FLIGHT_DETAIL_TTL:
        return JSONResponse(content=entry.data)

    if icao24 not in _flight_detail_locks:
        _flight_detail_locks[icao24] = asyncio.Lock()
    lock = _flight_detail_locks[icao24]

    async with lock:
        entry = _flight_detail_cache.get(icao24)
        if entry and entry.data is not None and (time.monotonic() - entry.fetched_at) < _FLIGHT_DETAIL_TTL:
            return JSONResponse(content=entry.data)

        try:
            data = await _fetch_flight_detail(client, icao24, intel)
            _flight_detail_cache[icao24] = CacheEntry(
                data=data, fetched_at=time.monotonic(),
                record_count=len(data.get("track", [])), error=None,
            )
            if len(_flight_detail_cache) > 500:
                oldest_keys = sorted(
                    _flight_detail_cache.keys(),
                    key=lambda k: _flight_detail_cache[k].fetched_at,
                )[:100]
                for k in oldest_keys:
                    _flight_detail_cache.pop(k, None)
                    _flight_detail_locks.pop(k, None)
            return JSONResponse(content=data)
        except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
            logger.error("Flight detail fetch failed for %s: %s", icao24, exc)
            if entry and entry.data is not None:
                return JSONResponse(content=entry.data)
            return JSONResponse(content={"icao24": icao24, "state": None, "track": [], "error": str(exc)})
