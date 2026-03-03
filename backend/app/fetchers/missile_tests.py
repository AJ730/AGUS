"""Live missile strikes, bombings, and weapons test fetcher (ACLED + GDELT + Wikidata)."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher
from .conflicts import ConflictFetcher

logger = logging.getLogger("agus.fetchers")

# Historical test sites from Wikidata
_SPARQL = """
SELECT DISTINCT ?event ?eventLabel ?date ?countryLabel ?lat ?lon ?typeLabel WHERE {
  VALUES ?type { wd:Q10530571 wd:Q578948 wd:Q210112 }
  ?event wdt:P31 ?type .
  OPTIONAL { ?event wdt:P585 ?date . }
  OPTIONAL { ?event wdt:P17 ?country . }
  {
    ?event wdt:P625 ?coord .
  } UNION {
    ?event wdt:P276 ?loc .
    ?loc wdt:P625 ?coord .
  } UNION {
    ?event wdt:P17 ?c .
    ?c wdt:P625 ?coord .
  }
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 300
"""


class MissileTestFetcher(BaseFetcher):
    """Live missile/bombing events from ACLED + GDELT, with Wikidata historical tests."""

    async def _from_acled(self, client: httpx.AsyncClient) -> List[dict]:
        """Live missile strikes, airstrikes, drone strikes, shelling from ACLED."""
        if not ConflictFetcher._token:
            return []
        resp = await client.get(
            "https://acleddata.com/api/acled/read",
            headers={"Authorization": f"Bearer {ConflictFetcher._token}"},
            params={
                "limit": 1000,
                "event_type": "Explosions/Remote violence",
                "event_type_where": "=",
                "fields": "event_date|event_type|sub_event_type|actor1|actor2"
                          "|country|admin1|latitude|longitude|fatalities|notes|source",
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
            sub = r.get("sub_event_type", "")
            # Classify the sub-event type
            sub_lower = sub.lower()
            if "airstrike" in sub_lower or "air" in sub_lower:
                etype = "airstrike"
            elif "drone" in sub_lower:
                etype = "drone_strike"
            elif "shell" in sub_lower or "artillery" in sub_lower:
                etype = "shelling"
            elif "missile" in sub_lower:
                etype = "missile_strike"
            elif "suicide" in sub_lower:
                etype = "suicide_bombing"
            elif "ied" in sub_lower or "bomb" in sub_lower or "mine" in sub_lower:
                etype = "bombing"
            else:
                etype = "explosion"
            notes = r.get("notes", "")
            results.append({
                "name": notes[:120] if notes else sub or "Explosion/Remote Violence",
                "date": r.get("event_date", ""),
                "country": r.get("country", ""),
                "region": r.get("admin1", ""),
                "latitude": lat,
                "longitude": lon,
                "type": etype,
                "sub_type": sub,
                "actor": r.get("actor1", ""),
                "target": r.get("actor2", ""),
                "fatalities": int(r.get("fatalities", 0) or 0),
                "source": r.get("source", "ACLED"),
            })
        return results

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        """Breaking news about missile launches, airstrikes, bombings."""
        query = ('("missile strike" OR "airstrike" OR "drone strike" OR '
                 '"bombing" OR "missile launch" OR "ballistic missile")')
        features = await self._gdelt(client, query, "30D", 500)
        results: List[dict] = []
        for feat in features:
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates")
            if not coords:
                continue
            props = feat.get("properties") or {}
            name = props.get("name", props.get("title", "Strike/Bombing"))
            url = props.get("url", "")
            results.append({
                "name": name,
                "date": props.get("date", ""),
                "country": props.get("country", ""),
                "latitude": coords[1],
                "longitude": coords[0],
                "type": "strike_report",
                "sub_type": "news report",
                "actor": "",
                "target": "",
                "fatalities": 0,
                "source": "GDELT",
                "url": url,
            })
        return results

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        """Historical missile/nuclear test sites."""
        bindings = await self._wikidata(client, _SPARQL)
        results: List[dict] = []
        seen = set()
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            name = self._label(b, "eventLabel", "Test Event")
            key = f"{name}:{round(coords[0], 2)}:{round(coords[1], 2)}"
            if key in seen:
                continue
            seen.add(key)
            raw_type = self._label(b, "typeLabel", "").lower()
            etype = "nuclear_test" if "nuclear" in raw_type else "missile_test"
            date_str = self._label(b, "date")
            results.append({
                "name": name,
                "date": date_str[:10] if date_str else "",
                "country": self._label(b, "countryLabel"),
                "latitude": coords[0],
                "longitude": coords[1],
                "type": etype,
                "sub_type": raw_type,
                "actor": "",
                "target": "",
                "fatalities": 0,
                "source": "Wikidata",
            })
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._collect(
            client, self._from_acled, self._from_gdelt, self._from_wikidata,
        )
