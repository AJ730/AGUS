"""Global Forest Watch deforestation alerts fetcher.

Fetches GLAD/RADD deforestation alerts from the GFW API.
Free, no authentication required.
URL: https://data-api.globalforestwatch.org/
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_GFW_URL = "https://data-api.globalforestwatch.org/dataset/gfw_integrated_alerts/latest/query"
_TIMEOUT = httpx.Timeout(connect=15.0, read=45.0, write=5.0, pool=10.0)

# Key tropical forest regions with recent deforestation hotspots
_HOTSPOT_REGIONS = [
    {"name": "Amazon (Brazil)", "lat": -3.4, "lon": -60.0, "country": "Brazil"},
    {"name": "Amazon (Peru)", "lat": -10.0, "lon": -75.0, "country": "Peru"},
    {"name": "Amazon (Colombia)", "lat": 1.0, "lon": -72.0, "country": "Colombia"},
    {"name": "Congo Basin (DRC)", "lat": 0.0, "lon": 23.0, "country": "DRC"},
    {"name": "Congo Basin (Cameroon)", "lat": 4.0, "lon": 12.0, "country": "Cameroon"},
    {"name": "Borneo (Indonesia)", "lat": 0.0, "lon": 114.0, "country": "Indonesia"},
    {"name": "Sumatra (Indonesia)", "lat": -1.0, "lon": 102.0, "country": "Indonesia"},
    {"name": "Papua New Guinea", "lat": -6.0, "lon": 147.0, "country": "PNG"},
    {"name": "Myanmar Forests", "lat": 20.0, "lon": 96.0, "country": "Myanmar"},
    {"name": "Madagascar", "lat": -19.0, "lon": 47.0, "country": "Madagascar"},
    {"name": "Cerrado (Brazil)", "lat": -14.0, "lon": -47.0, "country": "Brazil"},
    {"name": "Chaco (Argentina)", "lat": -24.0, "lon": -61.0, "country": "Argentina"},
    {"name": "Mekong (Laos)", "lat": 18.0, "lon": 103.0, "country": "Laos"},
    {"name": "West Africa (Ghana)", "lat": 7.0, "lon": -1.5, "country": "Ghana"},
    {"name": "Central Kalimantan", "lat": -1.5, "lon": 113.0, "country": "Indonesia"},
]


class DeforestationFetcher(BaseFetcher):
    """Fetches deforestation alerts from Global Forest Watch + GDELT."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch deforestation data from GFW API + GDELT reports."""
        return await self._collect(
            client,
            self._fetch_gfw,
            self._fetch_gdelt_deforestation,
        )

    async def _fetch_gfw(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch from Global Forest Watch integrated alerts API."""
        results: List[dict] = []
        try:
            # GFW API uses SQL-like queries
            resp = await client.get(
                _GFW_URL,
                params={
                    "sql": "SELECT latitude, longitude, gfw_integrated_alerts__date, umd_glad_landsat_alerts__confidence, wur_radd_alerts__confidence FROM results LIMIT 200",
                    "format": "json",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("data", [])
            for row in rows:
                lat = row.get("latitude")
                lon = row.get("longitude")
                if lat is None or lon is None:
                    continue
                date = row.get("gfw_integrated_alerts__date", "")
                glad_conf = row.get("umd_glad_landsat_alerts__confidence", "")
                radd_conf = row.get("wur_radd_alerts__confidence", "")
                confidence = glad_conf or radd_conf or "low"

                results.append({
                    "name": f"Deforestation Alert ({date})",
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "date": str(date),
                    "confidence": str(confidence),
                    "severity": "High" if confidence in ("high", "highest", "3", "4") else "Medium",
                    "alert_type": "GLAD" if glad_conf else "RADD",
                    "source": "Global Forest Watch",
                })
            logger.info("Deforestation GFW: %d alerts", len(results))
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Deforestation GFW fetch failed: %s", exc)

        # If GFW API didn't work, use known hotspot regions
        if not results:
            for hs in _HOTSPOT_REGIONS:
                results.append({
                    "name": f"Deforestation Hotspot — {hs['name']}",
                    "latitude": hs["lat"],
                    "longitude": hs["lon"],
                    "country": hs["country"],
                    "severity": "High",
                    "confidence": "known_hotspot",
                    "alert_type": "Historical Hotspot",
                    "source": "GFW Known Hotspots",
                })
        return results

    async def _fetch_gdelt_deforestation(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch deforestation news reports from GDELT (GEO + DOC fallback)."""
        results: List[dict] = []
        try:
            features = await self._gdelt(
                client,
                'deforestation OR "illegal logging" OR "forest fire" OR "land clearing"',
                timespan="14D",
                maxrows=50,
            )
            for feat in features[:30]:
                coords = feat.get("geometry", {}).get("coordinates", [])
                props = feat.get("properties", {})
                if len(coords) < 2:
                    continue
                results.append({
                    "name": (props.get("name") or "Deforestation Report")[:120],
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "severity": "Medium",
                    "confidence": "media_report",
                    "date": props.get("date", props.get("urlpubtimedate", "")),
                    "url": props.get("url", ""),
                    "alert_type": "News Report",
                    "source": "GDELT",
                })
            logger.info("Deforestation GDELT: %d reports", len(results))
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Deforestation GDELT fetch failed: %s", exc)
        return results
