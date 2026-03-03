"""UNHCR refugee displacement data fetcher."""

from __future__ import annotations

import logging
from typing import List

import httpx

from ..utils import COUNTRY_COORDS
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")


class RefugeeFetcher(BaseFetcher):
    """Fetches refugee data from UNHCR Population API with GDELT fallback."""

    async def _from_unhcr(self, client: httpx.AsyncClient) -> List[dict]:
        resp = await client.get(
            "https://api.unhcr.org/population/v1/population/",
            params={"limit": 500, "yearFrom": 2023, "yearTo": 2024, "coo_all": True},
            headers={"Accept": "application/json"}, timeout=20.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("items") or payload.get("data") or []
        if not items and isinstance(payload, list):
            items = payload
        agg: dict = {}
        for item in items:
            country = item.get("coo_name") or item.get("coa_name") or ""
            if not country or country == "-":
                continue
            pop = 0
            for field in ("refugees", "asylum_seekers", "idps"):
                val = item.get(field) or 0
                try:
                    pop += int(val)
                except (ValueError, TypeError):
                    pass
            if country in agg:
                agg[country] += pop
            else:
                agg[country] = pop
        results: List[dict] = []
        for country, pop in agg.items():
            coords = COUNTRY_COORDS.get(country, COUNTRY_COORDS.get(country.lower()))
            if not coords:
                continue
            lat, lon = coords
            results.append({
                "title": f"Displaced from {country}",
                "country": country, "latitude": lat, "longitude": lon,
                "population_affected": pop, "date": "2024",
            })
        return results

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        query = "(refugee OR displacement OR asylum)"
        features = await self._gdelt(client, query, "30D", 200)
        return [{
            "title": (f.get("properties") or {}).get("name", "Displacement"),
            "country": "",
            "latitude": f["geometry"]["coordinates"][1],
            "longitude": f["geometry"]["coordinates"][0],
            "population_affected": None, "date": "",
        } for f in features if (f.get("geometry") or {}).get("coordinates")]

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(client, self._from_unhcr, self._from_gdelt)
