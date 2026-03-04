"""Iran-focused OSINT aggregator — GDELT + Wikidata military installations + Overpass."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

# Iran military installation SPARQL (IRGC bases, missile facilities, nuclear sites)
_IRAN_SPARQL = """
SELECT DISTINCT ?item ?itemLabel ?lat ?lon ?typeLabel WHERE {
  ?item wdt:P17 wd:Q794 .  # Located in Iran
  {
    ?item wdt:P31/wdt:P279* wd:Q18691599 .  # military base
  } UNION {
    ?item wdt:P31/wdt:P279* wd:Q174174 .   # nuclear facility
  } UNION {
    ?item wdt:P31/wdt:P279* wd:Q245016 .   # military installation
  } UNION {
    ?item wdt:P31/wdt:P279* wd:Q1248784 .  # airport (military)
    ?item wdt:P137 ?operator .
    FILTER(CONTAINS(LCASE(STR(?operator)), "military") || CONTAINS(LCASE(STR(?operator)), "army") || CONTAINS(LCASE(STR(?operator)), "air force"))
  }
  ?item wdt:P625 ?coord .
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 200
"""


class IranOSINTFetcher(BaseFetcher):
    """Iran-focused OSINT: military installations, GDELT reports, facility tracking."""

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        """Iran-focused GDELT breaking news."""
        query = ('("Iran missile" OR "IRGC" OR "Tehran military" OR '
                 '"Iran nuclear" OR "Iranian drone" OR "Natanz" OR '
                 '"Isfahan military" OR "Parchin" OR "Bandar Abbas" OR '
                 '"Strait of Hormuz" OR "Iran Israel")')
        features = await self._gdelt(client, query, "30D", 300)
        results: List[dict] = []
        for feat in features:
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates")
            if not coords:
                continue
            props = feat.get("properties") or {}
            results.append({
                "title": props.get("name", "Iran OSINT Report"),
                "latitude": coords[1],
                "longitude": coords[0],
                "country": "Iran",
                "category": "iran_osint",
                "severity": "high",
                "date": props.get("date", ""),
                "url": props.get("url", ""),
                "source": props.get("source", "GDELT"),
                "type": "iran_osint",
            })
        return results

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        """Iranian military installations from Wikidata."""
        bindings = await self._wikidata(client, _IRAN_SPARQL)
        results: List[dict] = []
        seen = set()
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            name = self._label(b, "itemLabel", "Military Facility")
            key = f"{round(coords[0], 2)}:{round(coords[1], 2)}"
            if key in seen:
                continue
            seen.add(key)
            facility_type = self._label(b, "typeLabel", "military installation")
            results.append({
                "title": f"[IRAN] {name}",
                "latitude": coords[0],
                "longitude": coords[1],
                "country": "Iran",
                "category": "iran_military",
                "severity": "high",
                "type": "iran_osint",
                "sub_type": facility_type,
                "source": "Wikidata",
            })
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._collect(client, self._from_gdelt, self._from_wikidata)
