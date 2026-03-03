"""Military base location fetcher (Overpass, Wikidata)."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_OVERPASS_QUERY = ('[out:json][timeout:90];'
                   'node["military"~"airfield|barracks|naval_base|base"];'
                   'out body qt 3000;')

_SPARQL = """
SELECT ?base ?baseLabel ?lat ?lon ?countryLabel WHERE {
  ?base wdt:P31 wd:Q18691599 .
  ?base wdt:P625 ?coord .
  OPTIONAL { ?base wdt:P17 ?country . }
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 1000
"""


class MilitaryBaseFetcher(BaseFetcher):
    """Fetches military base locations from Overpass with Wikidata fallback."""

    async def _from_overpass(self, client: httpx.AsyncClient) -> List[dict]:
        elements = await self._overpass(client, _OVERPASS_QUERY)
        results: List[dict] = []
        for el in elements:
            lat, lon = el.get("lat"), el.get("lon")
            if lat is None or lon is None:
                continue
            tags = el.get("tags") or {}
            results.append({
                "name": tags.get("name", "Military Installation"),
                "country": tags.get("addr:country", ""),
                "operator": tags.get("operator", ""),
                "latitude": lat, "longitude": lon,
                "type": tags.get("military", "base"),
                "branch": tags.get("operator", ""), "status": "active",
            })
        return results

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        bindings = await self._wikidata(client, _SPARQL)
        results: List[dict] = []
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            results.append({
                "name": self._label(b, "baseLabel", "Military Base"),
                "country": self._label(b, "countryLabel"),
                "operator": "", "latitude": coords[0], "longitude": coords[1],
                "type": "base", "branch": "", "status": "active",
            })
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(client, self._from_overpass, self._from_wikidata)
