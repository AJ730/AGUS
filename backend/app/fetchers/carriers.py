"""Aircraft carrier and major warship fetcher (Wikidata + GDELT)."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

# Carriers, helicopter carriers, amphibious assault ships, cruisers
_SPARQL = """
SELECT DISTINCT ?ship ?shipLabel ?classLabel ?operatorLabel ?portLabel ?lat ?lon WHERE {
  VALUES ?type { wd:Q17205 wd:Q2526255 wd:Q743004 wd:Q1792159 wd:Q1786616 wd:Q174736 }
  ?ship wdt:P31 ?type .
  FILTER NOT EXISTS { ?ship wdt:P793 wd:Q52706 . }
  { ?ship wdt:P625 ?coord . } UNION { ?ship wdt:P504 ?port . ?port wdt:P625 ?coord . }
  OPTIONAL { ?ship wdt:P289 ?class . }
  OPTIONAL { ?ship wdt:P137 ?operator . }
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 500
"""

# Filter out defunct/historical navies in Python
_DEFUNCT_NAVIES = frozenset([
    "imperial japanese navy", "kriegsmarine", "imperial german navy",
    "regia marina", "royal italian navy", "imperial russian navy",
    "soviet navy", "ottoman navy", "austro-hungarian navy",
    "confederate states navy", "free french naval forces",
])


class CarrierFetcher(BaseFetcher):
    """Fetches aircraft carrier and major warship locations from Wikidata + GDELT."""

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        bindings = await self._wikidata(client, _SPARQL)
        results, seen = [], set()
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            operator = self._label(b, "operatorLabel")
            if operator.lower() in _DEFUNCT_NAVIES:
                continue
            key = f"{round(coords[0], 2)}:{round(coords[1], 2)}"
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "name": self._label(b, "shipLabel", "Warship"),
                "class": self._label(b, "classLabel"),
                "operator": operator,
                "home_port": self._label(b, "portLabel"),
                "latitude": coords[0], "longitude": coords[1],
                "type": "carrier", "status": "active",
            })
        return results

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        query = ('("aircraft carrier" OR "carrier strike group" OR '
                 '"naval fleet" OR "warship" OR "destroyer deployed" OR '
                 '"navy deployment" OR "naval task force")')
        features = await self._gdelt(client, query, "30D", 300)
        return [{
            "name": (f.get("properties") or {}).get("name", "Naval Activity"),
            "class": "", "operator": "",
            "home_port": "",
            "latitude": f["geometry"]["coordinates"][1],
            "longitude": f["geometry"]["coordinates"][0],
            "type": "carrier", "status": "reported",
        } for f in features if (f.get("geometry") or {}).get("coordinates")]

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._collect(client, self._from_wikidata, self._from_gdelt)
