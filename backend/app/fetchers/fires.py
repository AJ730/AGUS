"""NASA FIRMS active fire hotspot fetcher."""

from __future__ import annotations

import csv
import io
import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_URL = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_24h.csv"


class FireFetcher(BaseFetcher):
    """Fetches active fire hotspots from NASA FIRMS MODIS data."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        try:
            resp = await client.get(_URL, timeout=20.0)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            results: List[dict] = []
            for row in reader:
                try:
                    lat = float(row.get("latitude", 0))
                    lon = float(row.get("longitude", 0))
                    brightness = float(row.get("brightness", 0))
                except (ValueError, TypeError):
                    continue
                results.append({
                    "latitude": lat, "longitude": lon,
                    "brightness": brightness,
                    "confidence": row.get("confidence", ""),
                    "acq_date": row.get("acq_date", ""),
                    "satellite": row.get("satellite", ""),
                })
            return results
        except Exception as exc:
            logger.warning("NASA FIRMS fetch failed: %s", exc)
        return []
