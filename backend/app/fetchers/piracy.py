"""Maritime piracy event fetcher with GDELT primary and hotspot fallback."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_QUERY = '(piracy OR "maritime attack" OR hijacking OR "ship seizure")'

_PIRACY_HOTSPOTS = [
    {"title": "Gulf of Aden / Somali Basin", "latitude": 12.0, "longitude": 48.0, "severity": "high", "region": "Horn of Africa"},
    {"title": "Gulf of Guinea", "latitude": 4.0, "longitude": 2.0, "severity": "high", "region": "West Africa"},
    {"title": "Strait of Malacca", "latitude": 2.5, "longitude": 101.5, "severity": "medium", "region": "Southeast Asia"},
    {"title": "Singapore Strait", "latitude": 1.2, "longitude": 104.0, "severity": "medium", "region": "Southeast Asia"},
    {"title": "Bangladesh / Bay of Bengal", "latitude": 21.5, "longitude": 89.5, "severity": "medium", "region": "South Asia"},
    {"title": "South China Sea", "latitude": 10.0, "longitude": 114.0, "severity": "medium", "region": "Southeast Asia"},
    {"title": "Caribbean Sea", "latitude": 14.5, "longitude": -72.0, "severity": "low", "region": "Caribbean"},
    {"title": "Red Sea / Bab-el-Mandeb", "latitude": 13.0, "longitude": 43.0, "severity": "high", "region": "Middle East"},
    {"title": "Mozambique Channel", "latitude": -15.0, "longitude": 42.0, "severity": "medium", "region": "East Africa"},
    {"title": "Philippine Sea", "latitude": 7.0, "longitude": 124.0, "severity": "medium", "region": "Southeast Asia"},
    {"title": "Niger Delta", "latitude": 5.0, "longitude": 6.0, "severity": "high", "region": "West Africa"},
    {"title": "Peru / Callao Anchorage", "latitude": -12.0, "longitude": -77.1, "severity": "low", "region": "South America"},
]


class PiracyFetcher(BaseFetcher):
    """Fetches maritime piracy and hijacking events from GDELT with hotspot fallback."""

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        features = await self._gdelt(client, _QUERY, "30D", 200)
        results: List[dict] = []
        for feat in features:
            coords = (feat.get("geometry") or {}).get("coordinates")
            if not coords:
                continue
            props = feat.get("properties") or {}
            results.append({
                "title": props.get("name", props.get("title", "Maritime incident")),
                "latitude": coords[1], "longitude": coords[0],
                "date": props.get("date", props.get("urlpubtimedate", "")),
                "description": props.get("name", ""),
                "severity": "medium",
                "region": props.get("country", ""),
            })
        return results

    async def _from_hotspots(self, client: httpx.AsyncClient) -> List[dict]:
        return [
            {
                "title": h["title"],
                "latitude": h["latitude"],
                "longitude": h["longitude"],
                "date": "",
                "description": f"Known piracy hotspot - {h['region']}",
                "severity": h["severity"],
                "region": h["region"],
            }
            for h in _PIRACY_HOTSPOTS
        ]

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(client, self._from_gdelt, self._from_hotspots)
