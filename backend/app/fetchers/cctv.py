"""CCTV/webcam camera fetcher (Windy, Overpass, GDELT)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

# Major regions to query for surveillance cameras (global is too large)
_REGIONS = [
    (48.5, 2.0, 51.6, 7.0),    # W. Europe (Paris/London/Brussels)
    (40.4, -4.0, 43.8, 2.5),   # Spain/S. France
    (51.3, 6.5, 54.0, 14.5),   # Germany/Netherlands
    (41.8, 12.0, 45.6, 18.5),  # Italy
    (35.5, 139.0, 36.0, 140.0),  # Tokyo
    (31.0, 121.0, 31.5, 121.8),  # Shanghai
    (22.2, 113.8, 22.6, 114.4),  # Hong Kong
    (40.5, -74.3, 41.0, -73.7),  # NYC
    (33.7, -118.5, 34.2, -118.0),  # LA
    (-33.9, 150.9, -33.7, 151.3),  # Sydney
    (55.5, 37.3, 55.9, 37.9),  # Moscow
    (1.2, 103.6, 1.5, 104.0),  # Singapore
    (25.1, 55.0, 25.4, 55.5),  # Dubai
    (19.0, 72.7, 19.3, 73.0),  # Mumbai
]


class CCTVFetcher(BaseFetcher):
    """Fetches surveillance/traffic cameras from Windy, Overpass, or GDELT."""

    async def _from_windy(self, client: httpx.AsyncClient) -> List[dict]:
        key = os.getenv("WINDY_API_KEY", "")
        if not key:
            return []
        resp = await client.get(
            "https://api.windy.com/webcams/api/v3/webcams",
            headers={"x-windy-api-key": key},
            params={"limit": 500, "include": "location,player,urls"},
            timeout=15.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("webcams") or payload.get("result", {}).get("webcams", [])
        results: List[dict] = []
        for item in items:
            loc = item.get("location") or {}
            lat, lon = loc.get("latitude"), loc.get("longitude")
            if lat is None or lon is None:
                continue
            player = item.get("player") or {}
            stream = (player.get("live", {}).get("embed", "")
                      or player.get("day", {}).get("embed", "") or "")
            results.append({
                "name": item.get("title", "Webcam"), "city": loc.get("city", ""),
                "country": loc.get("country", ""), "region": loc.get("region", ""),
                "latitude": lat, "longitude": lon, "type": "webcam",
                "stream_url": stream, "status": item.get("status", ""),
                "source": "Windy",
            })
        return results

    async def _from_overpass(self, client: httpx.AsyncClient) -> List[dict]:
        bbox_strs = "".join(
            f"node[\"man_made\"=\"surveillance\"]({s},{w},{n},{e});"
            f"node[\"highway\"=\"speed_camera\"]({s},{w},{n},{e});"
            for s, w, n, e in _REGIONS
        )
        query = f'[out:json][timeout:90];({bbox_strs});out body qt 1000;'
        elements = await self._overpass(client, query)
        results: List[dict] = []
        for el in elements:
            lat, lon = el.get("lat"), el.get("lon")
            if lat is None or lon is None:
                continue
            tags = el.get("tags") or {}
            results.append({
                "name": tags.get("name", tags.get("operator", "Camera")),
                "city": tags.get("addr:city", ""),
                "country": tags.get("addr:country", ""),
                "latitude": lat, "longitude": lon,
                "type": tags.get("surveillance:type", "surveillance"),
                "operator": tags.get("operator", ""),
                "stream_url": tags.get("contact:webcam", tags.get("url", "")),
                "source": "OpenStreetMap",
            })
        return results

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        query = "(webcam OR surveillance OR CCTV)"
        features = await self._gdelt(client, query, "30D", 500)
        return [{
            "name": (f.get("properties") or {}).get("name", "Camera"),
            "city": "", "country": "",
            "latitude": f["geometry"]["coordinates"][1],
            "longitude": f["geometry"]["coordinates"][0],
            "type": "webcam", "stream_url": "", "source": "GDELT",
        } for f in features if (f.get("geometry") or {}).get("coordinates")]

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(
            client, self._from_windy, self._from_overpass, self._from_gdelt,
        )
