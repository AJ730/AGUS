"""Protest and civil unrest fetcher — ACLED + GDELT.

Fetches geocoded protest events worldwide.
ACLED requires free auth via OAuth (ACLED_EMAIL + ACLED_PASSWORD).
GDELT is free, no auth.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

import httpx

from ..config import ACLED_EMAIL, ACLED_PASSWORD
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_ACLED_URL = "https://acleddata.com/api/acled/read"
_TIMEOUT = httpx.Timeout(connect=15.0, read=45.0, write=5.0, pool=10.0)


class ProtestFetcher(BaseFetcher):
    """Fetches protest and civil unrest events from ACLED and GDELT."""

    _token: Optional[str] = None
    _token_expiry: float = 0.0

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch protests from ACLED + GDELT."""
        return await self._collect(
            client,
            self._fetch_acled_protests,
            self._fetch_gdelt_protests,
        )

    async def _get_acled_token(self, client: httpx.AsyncClient) -> Optional[str]:
        """Get ACLED OAuth token, cached until expiry."""
        if self._token and time.monotonic() < self._token_expiry:
            return self._token
        if not ACLED_EMAIL or not ACLED_PASSWORD:
            return None
        resp = await client.post(
            "https://acleddata.com/oauth/token",
            data={
                "username": ACLED_EMAIL,
                "password": ACLED_PASSWORD,
                "grant_type": "password",
                "client_id": "acled",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        ProtestFetcher._token = data.get("access_token")
        ProtestFetcher._token_expiry = time.monotonic() + data.get("expires_in", 86400) - 3600
        return self._token

    async def _fetch_acled_protests(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch protest events from ACLED API using OAuth."""
        token = await self._get_acled_token(client)
        if not token:
            return []
        results: List[dict] = []
        try:
            resp = await client.get(
                _ACLED_URL,
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "event_type": "Protests|Riots",
                    "event_type_where": "|",
                    "limit": 300,
                    "fields": "event_date|event_type|sub_event_type|actor1"
                              "|country|region|latitude|longitude|fatalities|notes",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("data") or (data if isinstance(data, list) else [])
            if isinstance(rows, dict):
                rows = rows.get("data") or []
            for ev in rows:
                lat = ev.get("latitude")
                lon = ev.get("longitude")
                if lat is None or lon is None:
                    continue
                try:
                    lat, lon = float(lat), float(lon)
                except (ValueError, TypeError):
                    continue
                if lat == 0 and lon == 0:
                    continue

                sub_type = ev.get("sub_event_type", "Protest")
                fatalities = int(ev.get("fatalities", 0) or 0)
                severity = (
                    "Critical" if fatalities > 10
                    else "High" if fatalities > 0
                    else "Medium" if "riot" in sub_type.lower() or "mob" in sub_type.lower()
                    else "Low"
                )

                results.append({
                    "name": (ev.get("notes") or sub_type or "Protest")[:120],
                    "latitude": lat,
                    "longitude": lon,
                    "event_type": ev.get("event_type", "Protest"),
                    "sub_type": sub_type,
                    "country": ev.get("country", ""),
                    "region": ev.get("region", ""),
                    "actor": ev.get("actor1", ""),
                    "fatalities": fatalities,
                    "severity": severity,
                    "date": ev.get("event_date", ""),
                    "source": "ACLED",
                })
            logger.info("Protests ACLED: %d events", len(results))
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Protests ACLED fetch failed: %s", exc)
        return results

    async def _fetch_gdelt_protests(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch protest reports from GDELT (GEO + DOC fallback)."""
        results: List[dict] = []
        try:
            features = await self._gdelt(
                client,
                "protest OR demonstration OR riot OR unrest",
                timespan="7D",
                maxrows=100,
            )
            for feat in features[:80]:
                coords = feat.get("geometry", {}).get("coordinates", [])
                props = feat.get("properties", {})
                if len(coords) < 2:
                    continue
                name = props.get("name", "Protest Report")
                results.append({
                    "name": str(name)[:120],
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "event_type": "Protest",
                    "sub_type": "Media Report",
                    "country": props.get("country", ""),
                    "severity": "Medium",
                    "date": props.get("date", props.get("urlpubtimedate", "")),
                    "url": props.get("url", ""),
                    "source": "GDELT",
                })
            logger.info("Protests GDELT: %d reports", len(results))
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Protests GDELT fetch failed: %s", exc)
        return results
