"""Nuclear plant and radiation monitoring fetcher."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_SPARQL = """
SELECT ?plant ?plantLabel ?lat ?lon ?countryLabel WHERE {
  VALUES ?type { wd:Q134447 wd:Q11424 wd:Q4654991 wd:Q18514864 }
  ?plant wdt:P31 ?type .
  ?plant wdt:P625 ?coord .
  OPTIONAL { ?plant wdt:P17 ?country . }
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 500
"""


class NuclearFetcher(BaseFetcher):
    """Fetches nuclear plants from Wikidata and radiation data from RadMon."""

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        bindings = await self._wikidata(client, _SPARQL)
        results: List[dict] = []
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            results.append({
                "station_name": self._label(b, "plantLabel", "Unknown"),
                "latitude": coords[0], "longitude": coords[1],
                "radiation_level": None, "unit": "uSv/h",
                "country": self._label(b, "countryLabel"),
                "last_reading": None, "status": "operational",
            })
        return results

    async def _from_radmon(self, client: httpx.AsyncClient) -> List[dict]:
        resp = await client.get(
            "https://radmon.org/index.php/api/json",
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
        )
        resp.raise_for_status()
        try:
            payload = resp.json()
        except (ValueError, KeyError):
            return []
        stations = payload if isinstance(payload, list) else []
        if isinstance(payload, dict):
            for key in ("data", "stations", "results"):
                if isinstance(payload.get(key), list):
                    stations = payload[key]
                    break
        results: List[dict] = []
        for s in stations:
            lat = s.get("lat") or s.get("latitude")
            lon = s.get("lon") or s.get("longitude")
            if lat is None or lon is None:
                continue
            try:
                lat, lon = float(lat), float(lon)
            except (ValueError, TypeError):
                continue
            results.append({
                "station_name": s.get("user", s.get("name", "Unknown")),
                "latitude": lat, "longitude": lon,
                "radiation_level": s.get("cpm") or s.get("value"),
                "unit": s.get("unit", "CPM"), "country": s.get("country", ""),
                "last_reading": s.get("timestamp"), "status": "online",
            })
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._collect(client, self._from_wikidata, self._from_radmon)
