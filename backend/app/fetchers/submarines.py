"""Submarine and naval base location fetcher (Wikidata, Overpass)."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_SPARQL = """
SELECT ?base ?baseLabel ?lat ?lon ?countryLabel ?operatorLabel WHERE {
  { ?base wdt:P31/wdt:P279* wd:Q18691599 . }
  UNION
  { ?base wdt:P31 wd:Q245016 . ?base wdt:P366 wd:Q2811 . }
  ?base wdt:P625 ?coord .
  OPTIONAL { ?base wdt:P17 ?country . }
  OPTIONAL { ?base wdt:P137 ?operator . }
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 200
"""

_OVERPASS_QUERY = '[out:json][timeout:60];node["military"="naval_base"];out body qt 500;'


class SubmarineFetcher(BaseFetcher):
    """Fetches submarine and naval base locations from Wikidata and Overpass."""

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        bindings = await self._wikidata(client, _SPARQL)
        results: List[dict] = []
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            results.append({
                "name": self._label(b, "baseLabel", "Naval Base"),
                "class": "Naval Base", "type": "submarine_base",
                "operator": self._label(b, "operatorLabel"),
                "country": self._label(b, "countryLabel"),
                "latitude": coords[0], "longitude": coords[1],
                "home_port": self._label(b, "baseLabel"), "status": "active",
            })
        return results

    async def _from_overpass(self, client: httpx.AsyncClient) -> List[dict]:
        elements = await self._overpass(client, _OVERPASS_QUERY)
        results: List[dict] = []
        for el in elements:
            lat, lon = el.get("lat"), el.get("lon")
            if lat is None or lon is None:
                continue
            tags = el.get("tags") or {}
            results.append({
                "name": tags.get("name", "Naval Base"),
                "class": "Naval Base", "type": "submarine_base",
                "operator": tags.get("operator", ""),
                "country": tags.get("addr:country", ""),
                "latitude": lat, "longitude": lon,
                "home_port": tags.get("name", ""), "status": "active",
            })
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        all_results = await self._collect(
            client, self._from_wikidata, self._from_overpass,
        )
        seen, unique = set(), []
        for r in all_results:
            key = f"{round(r['latitude'], 2)}:{round(r['longitude'], 2)}"
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
