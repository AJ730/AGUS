"""ACLED/GDELT terrorism and violence event fetcher."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher
from .conflicts import ConflictFetcher

logger = logging.getLogger("agus.fetchers")


class TerrorismFetcher(BaseFetcher):
    """Fetches terrorism/violence events from ACLED with GDELT fallback."""

    async def _from_acled(self, client: httpx.AsyncClient) -> List[dict]:
        if not ConflictFetcher._token:
            return []
        resp = await client.get(
            "https://acleddata.com/api/acled/read",
            headers={"Authorization": f"Bearer {ConflictFetcher._token}"},
            params={
                "limit": 500,
                "event_type": "Violence against civilians|Explosions/Remote violence",
                "event_type_where": "|",
                "fields": "event_date|event_type|sub_event_type|actor1|country"
                          "|latitude|longitude|fatalities|notes|source",
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data") or (payload if isinstance(payload, list) else [])
        if isinstance(rows, dict):
            rows = rows.get("data") or []
        results: List[dict] = []
        for r in rows:
            try:
                lat, lon = float(r.get("latitude", 0)), float(r.get("longitude", 0))
            except (ValueError, TypeError):
                continue
            if lat == 0 and lon == 0:
                continue
            notes = r.get("notes", "")
            results.append({
                "title": notes[:100] if notes else r.get("event_type", ""),
                "date": r.get("event_date", ""), "country": r.get("country", ""),
                "latitude": lat, "longitude": lon,
                "fatalities": int(r.get("fatalities", 0) or 0),
                "actor": r.get("actor1", ""), "source": r.get("source", "ACLED"),
                "theme": r.get("event_type", "Security"),
            })
        return results

    _TERROR_SPARQL = """
SELECT ?event ?eventLabel ?lat ?lon ?countryLabel ?date WHERE {
  { ?event wdt:P31 wd:Q2223653 . } UNION { ?event wdt:P31 wd:Q2916340 . }
  UNION { ?event wdt:P31 wd:Q891854 . }
  ?event wdt:P585 ?date .
  FILTER(YEAR(?date) >= 2022)
  { ?event wdt:P625 ?coord . }
  UNION
  { ?event wdt:P276 ?location . ?location wdt:P625 ?coord . }
  UNION
  { ?event wdt:P17 ?country . ?country wdt:P625 ?coord . }
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
} LIMIT 200
"""

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        bindings = await self._wikidata(client, self._TERROR_SPARQL)
        results: List[dict] = []
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            lat, lon = coords
            date_val = self._label(b, "date", "")
            results.append({
                "title": self._label(b, "eventLabel", "Security Event"),
                "date": date_val[:10] if date_val else "",
                "country": self._label(b, "countryLabel", ""),
                "latitude": lat, "longitude": lon,
                "fatalities": 0,
                "actor": "",
                "source": "Wikidata",
                "theme": "Security",
            })
        return results

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        query = '(terrorism OR bombing OR "suicide attack")'
        features = await self._gdelt(client, query, "30D", 300)
        return [{
            "title": (f.get("properties") or {}).get("name", "Security Event"),
            "country": (f.get("properties") or {}).get("name", ""),
            "latitude": f["geometry"]["coordinates"][1],
            "longitude": f["geometry"]["coordinates"][0],
            "source": "GDELT",
        } for f in features if (f.get("geometry") or {}).get("coordinates")]

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(client, self._from_acled, self._from_wikidata, self._from_gdelt)
