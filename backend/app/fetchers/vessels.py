"""Digitraffic AIS vessel position fetcher."""

from __future__ import annotations

import logging
from typing import List

import httpx

from ..config import MAX_VESSELS
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_URL = "https://meri.digitraffic.fi/api/ais/v1/locations"


class VesselFetcher(BaseFetcher):
    """Fetches live vessel positions from Digitraffic AIS API."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        try:
            resp = await client.get(_URL)
            resp.raise_for_status()
            features = resp.json().get("features") or []
            results: List[dict] = []
            for feat in features:
                if len(results) >= MAX_VESSELS:
                    break
                props = feat.get("properties") or {}
                coords = (feat.get("geometry") or {}).get("coordinates") or [None, None]
                if coords[0] is None or coords[1] is None:
                    continue
                ship_type = props.get("shipType")
                is_military_vessel = ship_type in (35, 55)
                results.append({
                    "mmsi": props.get("mmsi"),
                    "name": props.get("name", ""),
                    "latitude": coords[1], "longitude": coords[0],
                    "speed": props.get("sog"),
                    "heading": props.get("cog"),
                    "ship_type": ship_type,
                    "is_military": is_military_vessel,
                    "nav_status": props.get("navStat"),
                })
            return results
        except Exception as exc:
            logger.warning("Digitraffic vessel fetch failed: %s", exc)
        return []
