"""NOTAM and flight restriction fetcher with GDELT primary and Wikidata fallback."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_QUERY = '(NOTAM OR "airspace closure" OR "flight restriction" OR TFR)'

_NOTAM_SPARQL = """
SELECT ?item ?itemLabel ?lat ?lon ?countryLabel WHERE {
  { ?item wdt:P31 wd:Q7373622 . }
  UNION { ?item wdt:P31 wd:Q1402592 . }
  ?item wdt:P625 ?coord .
  OPTIONAL { ?item wdt:P17 ?country . }
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
} LIMIT 200
"""


class NOTAMFetcher(BaseFetcher):
    """Fetches NOTAM and flight restriction events from GDELT with Wikidata fallback."""

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        features = await self._gdelt(client, _QUERY, "30D", 200)
        results: List[dict] = []
        for feat in features:
            coords = (feat.get("geometry") or {}).get("coordinates")
            if not coords:
                continue
            props = feat.get("properties") or {}
            results.append({
                "title": props.get("name", props.get("title", "NOTAM")),
                "region": "",
                "latitude": coords[1], "longitude": coords[0],
                "type": "restriction",
                "description": props.get("name", ""),
            })
        return results

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        bindings = await self._wikidata(client, _NOTAM_SPARQL)
        results: List[dict] = []
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            lat, lon = coords
            label = self._label(b, "itemLabel", "Restricted Airspace")
            country = self._label(b, "countryLabel", "")
            results.append({
                "title": label,
                "region": country,
                "latitude": lat, "longitude": lon,
                "type": "restriction",
                "description": f"Military airfield / restricted airspace - {country}" if country else label,
            })
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(client, self._from_gdelt, self._from_wikidata)
