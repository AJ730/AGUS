"""Tropical cyclone fetcher — NHC + JTWC active storms.

Fetches active hurricanes, typhoons, and tropical storms.
Free, no authentication required.
URL: https://www.nhc.noaa.gov/CurrentSurges.json
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_NHC_URL = "https://www.nhc.noaa.gov/CurrentSurges.json"
_NHC_ACTIVE = "https://www.nhc.noaa.gov/gis/forecast/archive/"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)

# GDELT fallback for global cyclone reports
_GDELT_URL = "http://api.gdeltproject.org/api/v2/geo/geo"


class CycloneFetcher(BaseFetcher):
    """Fetches active tropical cyclone data from NHC and GDELT."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch active cyclones from NHC + GDELT fallback."""
        return await self._collect(
            client,
            self._fetch_nhc,
            self._fetch_gdelt_cyclones,
        )

    async def _fetch_nhc(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch from NHC active storms JSON feed."""
        results: List[dict] = []
        try:
            resp = await client.get(
                "https://www.nhc.noaa.gov/CurrentSurges.json",
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            storms = data.get("activeStorms") or []
            for storm in storms:
                lat = storm.get("latNumeric")
                lon = storm.get("lonNumeric")
                if lat is None or lon is None:
                    continue
                results.append({
                    "name": storm.get("name", "Unnamed Storm"),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "category": storm.get("classification", "Tropical Storm"),
                    "wind_speed": storm.get("intensity"),
                    "pressure": storm.get("pressure"),
                    "movement": storm.get("movementDir", ""),
                    "basin": "Atlantic/E.Pacific",
                    "source": "NHC/NOAA",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
            logger.warning("Cyclone NHC fetch failed: %s", exc)
        return results

    async def _fetch_gdelt_cyclones(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch cyclone/hurricane reports from GDELT GEO as fallback."""
        results: List[dict] = []
        try:
            resp = await client.get(
                _GDELT_URL,
                params={
                    "query": "hurricane OR typhoon OR cyclone OR tropical storm",
                    "mode": "PointData",
                    "format": "GeoJSON",
                    "maxpoints": 50,
                    "timespan": "7d",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            for feat in (data.get("features") or [])[:30]:
                coords = feat.get("geometry", {}).get("coordinates", [])
                props = feat.get("properties", {})
                if len(coords) < 2:
                    continue
                name = props.get("name", "Cyclone Report")
                results.append({
                    "name": name[:100],
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "category": "Tropical System (GDELT)",
                    "wind_speed": None,
                    "pressure": None,
                    "movement": "",
                    "basin": "Global",
                    "date": props.get("urlpubtimedate", ""),
                    "url": props.get("url", ""),
                    "source": "GDELT",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Cyclone GDELT fetch failed: %s", exc)
        return results
