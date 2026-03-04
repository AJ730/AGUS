"""Open-Meteo Air Quality API fetcher.

Fetches PM2.5, PM10, O3, NO2, and US AQI for major world cities.
Free, no authentication required.
URL: https://air-quality-api.open-meteo.com/v1/air-quality
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Tuple

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)

# Major cities: (name, lat, lon)
_CITIES: List[Tuple[str, float, float]] = [
    ("New York", 40.71, -74.01), ("London", 51.51, -0.13),
    ("Tokyo", 35.68, 139.69), ("Beijing", 39.91, 116.40),
    ("Delhi", 28.61, 77.21), ("Paris", 48.86, 2.35),
    ("Cairo", 30.04, 31.24), ("Moscow", 55.76, 37.62),
    ("Shanghai", 31.23, 121.47), ("Mumbai", 19.08, 72.88),
    ("Sao Paulo", -23.55, -46.63), ("Lagos", 6.52, 3.38),
    ("Istanbul", 41.01, 28.98), ("Seoul", 37.57, 126.98),
    ("Mexico City", 19.43, -99.13), ("Jakarta", -6.21, 106.85),
    ("Los Angeles", 34.05, -118.24), ("Bangkok", 13.76, 100.50),
    ("Berlin", 52.52, 13.41), ("Dubai", 25.20, 55.27),
    ("Singapore", 1.35, 103.82), ("Sydney", -33.87, 151.21),
    ("Chicago", 41.88, -87.63), ("Karachi", 24.86, 67.01),
    ("Hong Kong", 22.32, 114.17), ("Dhaka", 23.81, 90.41),
    ("Lima", -12.05, -77.04), ("Toronto", 43.65, -79.38),
    ("Riyadh", 24.69, 46.72), ("Madrid", 40.42, -3.70),
    ("Rome", 41.90, 12.50), ("Baghdad", 33.31, 44.37),
    ("Kyiv", 50.45, 30.52), ("Tehran", 35.69, 51.39),
    ("Lahore", 31.55, 74.35), ("Bogota", 4.71, -74.07),
    ("Kinshasa", -4.44, 15.27), ("Nairobi", -1.29, 36.82),
    ("Ho Chi Minh", 10.82, 106.63), ("Warsaw", 52.23, 21.01),
    ("Kabul", 34.53, 69.17), ("Addis Ababa", 9.02, 38.75),
    ("Ankara", 39.93, 32.86), ("Buenos Aires", -34.60, -58.38),
    ("Taipei", 25.03, 121.57), ("Manila", 14.60, 120.98),
    ("Kolkata", 22.57, 88.36), ("Cape Town", -33.93, 18.42),
    ("Johannesburg", -26.20, 28.05), ("Casablanca", 33.57, -7.59),
]

# Batch size for concurrent requests (avoid overwhelming the free API)
_BATCH_SIZE = 25


class AirQualityFetcher(BaseFetcher):
    """Fetches air quality data for major world cities from Open-Meteo."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch AQI data in batches for ~50 cities."""
        results: List[dict] = []

        # Split cities into batches
        for i in range(0, len(_CITIES), _BATCH_SIZE):
            batch = _CITIES[i:i + _BATCH_SIZE]
            tasks = [self._fetch_city(client, name, lat, lon) for name, lat, lon in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in batch_results:
                if isinstance(r, dict):
                    results.append(r)
            if i + _BATCH_SIZE < len(_CITIES):
                await asyncio.sleep(0.5)

        logger.info("AirQuality: %d cities fetched", len(results))
        return results

    async def _fetch_city(
        self, client: httpx.AsyncClient, name: str, lat: float, lon: float
    ) -> dict:
        """Fetch AQ data for a single city."""
        try:
            resp = await client.get(
                _AQ_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "us_aqi,pm2_5,pm10,ozone,nitrogen_dioxide",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})
            aqi = current.get("us_aqi", 0) or 0
            aqi_level = (
                "Hazardous" if aqi > 300
                else "Very Unhealthy" if aqi > 200
                else "Unhealthy" if aqi > 150
                else "Unhealthy (Sensitive)" if aqi > 100
                else "Moderate" if aqi > 50
                else "Good"
            )
            return {
                "name": f"{name} — AQI {aqi}",
                "city": name,
                "latitude": lat,
                "longitude": lon,
                "aqi": aqi,
                "aqi_level": aqi_level,
                "pm25": current.get("pm2_5"),
                "pm10": current.get("pm10"),
                "ozone": current.get("ozone"),
                "no2": current.get("nitrogen_dioxide"),
                "source": "Open-Meteo AQ",
            }
        except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
            logger.warning("AirQuality [%s]: %s", name, exc)
            return {
                "name": f"{name} — AQI N/A",
                "city": name,
                "latitude": lat,
                "longitude": lon,
                "aqi": 0,
                "aqi_level": "Unknown",
                "source": "Open-Meteo AQ",
            }
