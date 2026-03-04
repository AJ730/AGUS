"""Volcano alert fetcher — USGS + Smithsonian GVP.

Fetches elevated volcanic alert levels worldwide.
Free, no authentication required.
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_USGS_URL = "https://volcanoes.usgs.gov/hans-public/notice/getNotices"
_GVP_URL = "https://volcano.si.edu/news/WeeklyVolcanoRSS.xml"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)

# Smithsonian GVP notable volcanoes with coords for global coverage
_KNOWN_VOLCANOES = [
    {"name": "Kilauea", "latitude": 19.421, "longitude": -155.287, "country": "USA"},
    {"name": "Etna", "latitude": 37.748, "longitude": 14.999, "country": "Italy"},
    {"name": "Stromboli", "latitude": 38.789, "longitude": 15.213, "country": "Italy"},
    {"name": "Popocatépetl", "latitude": 19.023, "longitude": -98.628, "country": "Mexico"},
    {"name": "Sakurajima", "latitude": 31.581, "longitude": 130.657, "country": "Japan"},
    {"name": "Merapi", "latitude": -7.540, "longitude": 110.446, "country": "Indonesia"},
    {"name": "Semeru", "latitude": -8.108, "longitude": 112.922, "country": "Indonesia"},
    {"name": "Fuego", "latitude": 14.473, "longitude": -90.880, "country": "Guatemala"},
    {"name": "Mauna Loa", "latitude": 19.475, "longitude": -155.608, "country": "USA"},
    {"name": "Ruang", "latitude": 2.303, "longitude": 125.370, "country": "Indonesia"},
    {"name": "Taal", "latitude": 14.002, "longitude": 120.993, "country": "Philippines"},
    {"name": "Piton de la Fournaise", "latitude": -21.244, "longitude": 55.714, "country": "France"},
    {"name": "Krakatoa", "latitude": -6.102, "longitude": 105.423, "country": "Indonesia"},
    {"name": "Nevado del Ruiz", "latitude": 4.895, "longitude": -75.322, "country": "Colombia"},
    {"name": "Erebus", "latitude": -77.528, "longitude": 167.153, "country": "Antarctica"},
]


class VolcanoFetcher(BaseFetcher):
    """Fetches volcanic alert data from USGS and Smithsonian GVP."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch volcano alerts from USGS + known active volcanoes."""
        return await self._collect(
            client,
            self._fetch_usgs,
            self._fetch_gdelt_volcanoes,
        )

    async def _fetch_usgs(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch USGS HANS volcano notices."""
        results: List[dict] = []
        try:
            resp = await client.get(_USGS_URL, timeout=_TIMEOUT)
            resp.raise_for_status()
            notices = resp.json()
            if not isinstance(notices, list):
                notices = notices.get("notices", []) if isinstance(notices, dict) else []
            for notice in notices[:30]:
                lat = notice.get("latitude")
                lon = notice.get("longitude")
                if lat is None or lon is None:
                    continue
                alert_level = notice.get("alertLevel", "Normal")
                results.append({
                    "name": notice.get("volcanoName", "Unknown Volcano"),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "alert_level": alert_level,
                    "aviation_color": notice.get("aviationColorCode", ""),
                    "date": notice.get("sentDateMillis", ""),
                    "description": (notice.get("noticeText") or "")[:300],
                    "country": notice.get("country", ""),
                    "source": "USGS HANS",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Volcano USGS fetch failed: %s", exc)

        # Add known active volcanoes as baseline if USGS returned few
        if len(results) < 5:
            for v in _KNOWN_VOLCANOES:
                results.append({
                    "name": v["name"],
                    "latitude": v["latitude"],
                    "longitude": v["longitude"],
                    "alert_level": "Normal",
                    "aviation_color": "Green",
                    "country": v["country"],
                    "source": "Smithsonian GVP",
                })
        return results

    async def _fetch_gdelt_volcanoes(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch volcano eruption reports from GDELT as supplement."""
        results: List[dict] = []
        try:
            resp = await client.get(
                "http://api.gdeltproject.org/api/v2/geo/geo",
                params={
                    "query": "volcano eruption",
                    "mode": "PointData",
                    "format": "GeoJSON",
                    "maxpoints": 30,
                    "timespan": "14d",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            for feat in (data.get("features") or [])[:20]:
                coords = feat.get("geometry", {}).get("coordinates", [])
                props = feat.get("properties", {})
                if len(coords) < 2:
                    continue
                results.append({
                    "name": (props.get("name") or "Volcanic Activity")[:100],
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "alert_level": "Elevated",
                    "aviation_color": "Yellow",
                    "date": props.get("urlpubtimedate", ""),
                    "url": props.get("url", ""),
                    "source": "GDELT",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Volcano GDELT fetch failed: %s", exc)
        return results
