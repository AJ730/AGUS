"""USGS earthquake data fetcher."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"


class EarthquakeFetcher(BaseFetcher):
    """Fetches recent M2.5+ earthquakes from USGS GeoJSON feed."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        try:
            resp = await client.get(_URL)
            resp.raise_for_status()
            features = resp.json().get("features") or []
            results: List[dict] = []
            for feat in features:
                props = feat.get("properties") or {}
                coords = (feat.get("geometry") or {}).get("coordinates") or [None, None, None]
                if coords[0] is None or coords[1] is None:
                    continue
                results.append({
                    "magnitude": props.get("mag"),
                    "place": props.get("place", ""),
                    "time": props.get("time"),
                    "latitude": coords[1], "longitude": coords[0],
                    "depth": coords[2],
                    "tsunami_warning": bool(props.get("tsunami", 0)),
                    "felt": props.get("felt"),
                    "significance": props.get("sig"),
                })
            return results
        except Exception as exc:
            logger.warning("USGS earthquake fetch failed: %s", exc)
        return []
