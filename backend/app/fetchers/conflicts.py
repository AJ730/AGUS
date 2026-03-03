"""ACLED conflict event fetcher with GDELT fallback."""

from __future__ import annotations

import logging
import os
import time
from typing import List, Optional

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")


class ConflictFetcher(BaseFetcher):
    """Fetches conflict events from ACLED (OAuth) with GDELT fallback."""

    _token: Optional[str] = None
    _token_expiry: float = 0.0

    async def _get_acled_token(self, client: httpx.AsyncClient) -> Optional[str]:
        if self._token and time.monotonic() < self._token_expiry:
            return self._token
        email = os.getenv("ACLED_EMAIL", "")
        password = os.getenv("ACLED_PASSWORD", "")
        if not email or not password:
            return None
        resp = await client.post(
            "https://acleddata.com/oauth/token",
            data={"username": email, "password": password,
                  "grant_type": "password", "client_id": "acled"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        ConflictFetcher._token = data.get("access_token")
        ConflictFetcher._token_expiry = time.monotonic() + data.get("expires_in", 86400) - 3600
        return self._token

    async def _from_acled(self, client: httpx.AsyncClient) -> List[dict]:
        token = await self._get_acled_token(client)
        if not token:
            return []
        resp = await client.get(
            "https://acleddata.com/api/acled/read",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "limit": 2000,
                "fields": "event_date|event_type|sub_event_type|actor1|actor2"
                          "|country|admin1|admin2|admin3|latitude|longitude"
                          "|fatalities|notes|source",
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
            admin = [r.get("admin1", ""), r.get("admin2", ""), r.get("admin3", "")]
            results.append({
                "event_date": r.get("event_date", ""),
                "event_type": r.get("event_type", "Conflict"),
                "sub_event_type": r.get("sub_event_type", ""),
                "actor1": r.get("actor1", ""), "actor2": r.get("actor2", ""),
                "country": r.get("country", "Unknown"),
                "location": ", ".join(p for p in admin if p),
                "latitude": lat, "longitude": lon,
                "fatalities": int(r.get("fatalities", 0) or 0),
                "notes": r.get("notes", ""), "source": r.get("source", "ACLED"),
            })
        return results

    _CONFLICT_SPARQL = """
SELECT ?conflict ?conflictLabel ?lat ?lon ?countryLabel ?startDate WHERE {
  { ?conflict wdt:P31 wd:Q350604 . } UNION { ?conflict wdt:P31 wd:Q645883 . }
  ?conflict wdt:P580 ?startDate .
  FILTER(YEAR(?startDate) >= 2020)
  { ?conflict wdt:P625 ?coord . }
  UNION
  { ?conflict wdt:P276 ?location . ?location wdt:P625 ?coord . }
  UNION
  { ?conflict wdt:P17 ?country . ?country wdt:P625 ?coord . }
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
} LIMIT 200
"""

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        bindings = await self._wikidata(client, self._CONFLICT_SPARQL)
        results: List[dict] = []
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            lat, lon = coords
            results.append({
                "event_type": "Conflict",
                "country": self._label(b, "countryLabel", "Unknown"),
                "latitude": lat, "longitude": lon,
                "fatalities": 0,
                "notes": self._label(b, "conflictLabel", "Armed conflict"),
                "source": "Wikidata",
            })
        return results

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        query = "(conflict OR battle OR airstrike OR shelling)"
        features = await self._gdelt(client, query, "7D", 500)
        return [{
            "event_type": "Conflict",
            "country": (f.get("properties") or {}).get("name", "Unknown"),
            "latitude": f["geometry"]["coordinates"][1],
            "longitude": f["geometry"]["coordinates"][0],
            "fatalities": 0, "notes": "", "source": "GDELT",
        } for f in features if (f.get("geometry") or {}).get("coordinates")]

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(client, self._from_acled, self._from_wikidata, self._from_gdelt)
