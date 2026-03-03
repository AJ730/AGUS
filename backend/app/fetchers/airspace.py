"""Airspace restriction zone fetcher (OpenAIP, GDELT)."""

from __future__ import annotations

import logging
import os
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")


class AirspaceFetcher(BaseFetcher):
    """Fetches restricted airspace zones from OpenAIP with GDELT fallback."""

    async def _from_openaip(self, client: httpx.AsyncClient) -> List[dict]:
        key = os.getenv("OPENAIP_API_KEY", "")
        if not key:
            return []
        resp = await client.get(
            "https://api.core.openaip.net/api/airspaces",
            headers={"x-openaip-api-key": key},
            params={"type": "0,1,2,3,4,5", "limit": 500}, timeout=20.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("items") or (payload if isinstance(payload, list) else [])
        return [{
            "name": item.get("name", "Airspace"),
            "description": item.get("icaoClass", ""),
            "type": item.get("type", "unknown"),
            "geometry": item.get("geometry"),
            "properties": {"name": item.get("name"), "type": item.get("type"),
                           "status": "active"},
        } for item in items]

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        query = '("no fly zone" OR "airspace restriction")'
        features = await self._gdelt(client, query, "30D", 200)
        results: List[dict] = []
        for f in features:
            coords = (f.get("geometry") or {}).get("coordinates")
            if not coords:
                continue
            name = (f.get("properties") or {}).get("name", "Airspace Restriction")
            results.append({
                "name": name, "description": name, "type": "restriction",
                "geometry": {"type": "Point", "coordinates": [coords[0], coords[1]]},
                "properties": {"name": name, "type": "restriction", "status": "active"},
            })
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(client, self._from_openaip, self._from_gdelt)
