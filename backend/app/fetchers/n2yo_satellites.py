"""N2YO satellite tracker fetcher — live satellite positions.

Fetches real-time positions of notable satellites using the N2YO API.
Requires N2YO_API_KEY (free registration at n2yo.com/api).
URL: https://www.n2yo.com/rest/v1/satellite/
"""

from __future__ import annotations

import asyncio
import logging
from typing import List

import httpx

from ..config import N2YO_API_KEY
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_BASE_URL = "https://api.n2yo.com/rest/v1/satellite"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)

# Notable satellites to track — NORAD catalog IDs
# Mix of ISS, Chinese station, spy sats, weather, comms
_TRACKED_SATELLITES = [
    {"norad_id": 25544, "name": "ISS (ZARYA)", "category": "Space Station"},
    {"norad_id": 48274, "name": "CSS (Tianhe)", "category": "Space Station"},
    {"norad_id": 36516, "name": "SDO (Solar Dynamics Observatory)", "category": "Science"},
    {"norad_id": 43013, "name": "NOAA-20 (JPSS-1)", "category": "Weather"},
    {"norad_id": 27424, "name": "Envisat", "category": "Earth Observation"},
    {"norad_id": 28654, "name": "NOAA-18", "category": "Weather"},
    {"norad_id": 33591, "name": "NOAA-19", "category": "Weather"},
    {"norad_id": 25338, "name": "NOAA-15", "category": "Weather"},
    {"norad_id": 41866, "name": "GOES-16", "category": "Weather"},
    {"norad_id": 43226, "name": "GOES-17", "category": "Weather"},
    {"norad_id": 29155, "name": "Lacrosse 5", "category": "Reconnaissance"},
    {"norad_id": 37348, "name": "Tiangong (remnant)", "category": "Space Station"},
    {"norad_id": 40258, "name": "WorldView-3", "category": "Earth Observation"},
    {"norad_id": 44874, "name": "Starlink-1007", "category": "Communications"},
    {"norad_id": 56174, "name": "OneWeb-0541", "category": "Communications"},
    {"norad_id": 39084, "name": "Landsat 8", "category": "Earth Observation"},
    {"norad_id": 49260, "name": "Landsat 9", "category": "Earth Observation"},
    {"norad_id": 43600, "name": "ICESat-2", "category": "Science"},
    {"norad_id": 20580, "name": "Hubble Space Telescope", "category": "Science"},
    {"norad_id": 54216, "name": "JWST (James Webb)", "category": "Science"},
]

# Observer location for the API (center of globe, just needed for API call)
_OBS_LAT = 0.0
_OBS_LON = 0.0
_OBS_ALT = 0


class N2YOSatelliteFetcher(BaseFetcher):
    """Fetches real-time satellite positions from N2YO API."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch live positions of tracked satellites."""
        if not N2YO_API_KEY:
            logger.warning("N2YO: No API key configured (set N2YO_API_KEY)")
            return []

        results: List[dict] = []
        # N2YO free tier: 300 transactions/hour, batch carefully
        # Use positions endpoint: /positions/{id}/{observer_lat}/{observer_lng}/{observer_alt}/{seconds}
        # We request 1 second of positions (just current pos)

        semaphore = asyncio.Semaphore(3)  # max 3 concurrent requests

        async def _fetch_one(sat: dict) -> dict | None:
            async with semaphore:
                try:
                    url = (
                        f"{_BASE_URL}/positions/{sat['norad_id']}"
                        f"/{_OBS_LAT}/{_OBS_LON}/{_OBS_ALT}/1"
                        f"?apiKey={N2YO_API_KEY}"
                    )
                    resp = await client.get(url, timeout=_TIMEOUT)
                    resp.raise_for_status()
                    data = resp.json()

                    info = data.get("info", {})
                    positions = data.get("positions", [])
                    if not positions:
                        return None

                    pos = positions[0]
                    lat = pos.get("satlatitude")
                    lon = pos.get("satlongitude")
                    alt_km = pos.get("sataltitude", 0)

                    if lat is None or lon is None:
                        return None

                    return {
                        "name": info.get("satname", sat["name"]),
                        "norad_id": sat["norad_id"],
                        "latitude": float(lat),
                        "longitude": float(lon),
                        "altitude_km": float(alt_km),
                        "category": sat["category"],
                        "azimuth": pos.get("azimuth", 0),
                        "elevation": pos.get("elevation", 0),
                        "ra": pos.get("ra", 0),
                        "dec": pos.get("dec", 0),
                        "timestamp": pos.get("timestamp", 0),
                        "eclipsed": pos.get("eclipsed", False),
                        "source": "N2YO",
                    }
                except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
                    logger.warning("N2YO fetch failed for %s: %s", sat["name"], exc)
                    return None
                finally:
                    await asyncio.sleep(0.3)  # rate limiting

        tasks = [_fetch_one(sat) for sat in _TRACKED_SATELLITES]
        done = await asyncio.gather(*tasks, return_exceptions=True)

        for item in done:
            if isinstance(item, dict):
                results.append(item)

        logger.info("N2YO satellites: %d positions fetched", len(results))
        return results
