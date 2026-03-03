"""
Agus OSINT Backend -- API Routes
=====================================
All API endpoints as a FastAPI router.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .cache import CacheEntry, CacheManager
from .flight_intel import FlightIntelligence

logger = logging.getLogger("agus.routes")

router = APIRouter(prefix="/api")

# These will be injected by the server module via app.state
# Accessed at runtime through request.app.state


def _cache(request: Request) -> CacheManager:
    return request.app.state.cache_manager


def _client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def _fetcher_fns(request: Request) -> dict:
    return request.app.state.fetcher_fns


def _intel(request: Request) -> FlightIntelligence:
    return request.app.state.flight_intel


# Per-icao24 flight detail cache
_flight_detail_cache: Dict[str, CacheEntry] = {}
_flight_detail_locks: Dict[str, asyncio.Lock] = {}
_FLIGHT_DETAIL_TTL = 15.0


# ---------------------------------------------------------------------------
# Health & sources
# ---------------------------------------------------------------------------

@router.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": _cache(request).status(),
    }


@router.get("/sources")
async def sources(request: Request):
    return _cache(request).sources_list()


# ---------------------------------------------------------------------------
# Generic layer endpoint helper
# ---------------------------------------------------------------------------

async def _layer_response(request: Request, name: str) -> JSONResponse:
    cache = _cache(request)
    fns = _fetcher_fns(request)
    data = await cache.get(name, fns[name])
    return JSONResponse(
        content=data,
        headers={"X-Cache-Fresh": str(cache.slot(name).is_fresh).lower()},
    )


# ---------------------------------------------------------------------------
# Data endpoints
# ---------------------------------------------------------------------------

@router.get("/flights")
async def flights(request: Request):
    return await _layer_response(request, "flights")


@router.get("/conflicts")
async def conflicts(request: Request):
    return await _layer_response(request, "conflicts")


@router.get("/events")
async def events(request: Request):
    return await _layer_response(request, "events")


@router.get("/fires")
async def fires(request: Request):
    return await _layer_response(request, "fires")


@router.get("/vessels")
async def vessels(request: Request):
    return await _layer_response(request, "vessels")


@router.get("/cctv")
async def cctv(request: Request):
    return await _layer_response(request, "cctv")


@router.get("/satellites")
async def satellites(request: Request):
    return await _layer_response(request, "satellites")


@router.get("/earthquakes")
async def earthquakes(request: Request):
    return await _layer_response(request, "earthquakes")


@router.get("/nuclear")
async def nuclear(request: Request):
    return await _layer_response(request, "nuclear")


@router.get("/weather_alerts")
async def weather_alerts(request: Request):
    return await _layer_response(request, "weather_alerts")


@router.get("/terrorism")
async def terrorism(request: Request):
    return await _layer_response(request, "terrorism")


@router.get("/refugees")
async def refugees(request: Request):
    return await _layer_response(request, "refugees")


@router.get("/piracy")
async def piracy(request: Request):
    return await _layer_response(request, "piracy")


@router.get("/airspace")
async def airspace(request: Request):
    return await _layer_response(request, "airspace")


@router.get("/sanctions")
async def sanctions(request: Request):
    return await _layer_response(request, "sanctions")


@router.get("/cyber")
async def cyber(request: Request):
    return await _layer_response(request, "cyber")


@router.get("/military_bases")
async def military_bases(request: Request):
    return await _layer_response(request, "military_bases")


@router.get("/airports")
async def airports(request: Request):
    return await _layer_response(request, "airports")


@router.get("/notams")
async def notams(request: Request):
    return await _layer_response(request, "notams")


@router.get("/submarines")
async def submarines(request: Request):
    return await _layer_response(request, "submarines")


@router.get("/carriers")
async def carriers(request: Request):
    return await _layer_response(request, "carriers")


@router.get("/news")
async def news(request: Request):
    return await _layer_response(request, "news")


@router.get("/threat_intel")
async def threat_intel(request: Request):
    return await _layer_response(request, "threat_intel")


@router.get("/signals")
async def signals(request: Request):
    return await _layer_response(request, "signals")


@router.get("/missile_tests")
async def missile_tests(request: Request):
    return await _layer_response(request, "missile_tests")


# ---------------------------------------------------------------------------
# Flight detail endpoint (per-icao24 with track)
# ---------------------------------------------------------------------------

async def _fetch_flight_detail(client: httpx.AsyncClient, icao24: str, intel: FlightIntelligence) -> dict:
    """Fetch detailed state + track for a single aircraft using adsb.lol (free, no rate limit)."""
    result: dict = {"icao24": icao24, "state": None, "track": []}

    # Primary: adsb.lol single-aircraft lookup
    try:
        resp = await client.get(
            f"https://api.adsb.lol/v2/hex/{icao24}",
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
                "is_military": intel.is_military(callsign, icao24) or intel.is_military_dbflags(ac.get("dbFlags", 0)),
                "squawk_alert": intel.detect_squawk_alert(squawk) if squawk else None,
            }
    except Exception as exc:
        logger.warning("adsb.lol detail fetch failed for %s: %s", icao24, exc)

    # Track/trace from adsb.lol
    try:
        trace_resp = await client.get(
            f"https://api.adsb.lol/v2/point/25/0/250/hex/{icao24}",
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
        )
        trace_resp.raise_for_status()
        trace_data = trace_resp.json()
        trace_ac = (trace_data.get("ac") or [])
        # Build basic track from mlat/trace data if available
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
    except Exception as exc:
        logger.warning("adsb.lol trace fetch failed for %s: %s", icao24, exc)

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
        except Exception:
            pass  # OpenSky often 429s, silently fall through

    return result


@router.get("/flight_detail/{icao24}")
async def flight_detail(icao24: str, request: Request):
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
        except Exception as exc:
            logger.error("Flight detail fetch failed for %s: %s", icao24, exc)
            if entry and entry.data is not None:
                return JSONResponse(content=entry.data)
            return JSONResponse(content={"icao24": icao24, "state": None, "track": [], "error": str(exc)})
