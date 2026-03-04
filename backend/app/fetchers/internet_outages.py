"""Internet outage detection fetcher using IODA + GDELT fallback.

Primary: IODA (Internet Outage Detection and Analysis) by Georgia Tech.
Fallback: GDELT news for internet shutdown/blackout reports.

Internet outages correlate strongly with military operations, civil unrest,
and government censorship — making them a valuable OSINT signal.
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher
from ..utils import COUNTRY_COORDS

logger = logging.getLogger("agus.fetchers")

_IODA_BASE = "https://api.ioda.inetintel.cc.gatech.edu/v2"
_IODA_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)

# Countries of interest for monitoring (conflict zones + authoritarian regimes)
_MONITORED_COUNTRIES = [
    "AF", "BY", "CD", "CF", "CN", "CU", "EG", "ER", "ET", "GN",
    "IQ", "IR", "KP", "LB", "LY", "ML", "MM", "NE", "NG", "PK",
    "PS", "RU", "SD", "SO", "SS", "SY", "TD", "TM", "UA", "UZ",
    "VE", "YE", "ZW",
]


class InternetOutageFetcher(BaseFetcher):
    """Fetches internet outage data from IODA API with GDELT fallback."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch internet outages from IODA, falling back to GDELT."""
        return await self._try_sources(
            client,
            self._fetch_ioda,
            self._fetch_gdelt_outages,
        )

    async def _fetch_ioda(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch from IODA outages/alerts API."""
        results: List[dict] = []
        try:
            import time
            now = int(time.time())
            day_ago = now - 86400

            # IODA outages alerts endpoint (correct path: /v2/outages/alerts)
            resp = await client.get(
                f"{_IODA_BASE}/outages/alerts",
                params={
                    "from": str(day_ago),
                    "until": str(now),
                    "limit": 200,
                },
                timeout=_IODA_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                logger.debug("IODA outages/alerts returned %d, trying events", resp.status_code)
                return await self._fetch_ioda_events(client)

            data = resp.json()
            alerts = data if isinstance(data, list) else data.get("data", data.get("alerts", []))

            for alert in alerts:
                entity_type = alert.get("entity", {}).get("type", "")
                entity_code = alert.get("entity", {}).get("code", "")
                entity_name = alert.get("entity", {}).get("name", entity_code)

                # Get coordinates for country
                coords = COUNTRY_COORDS.get(entity_code) or COUNTRY_COORDS.get(entity_name)
                if not coords:
                    # Try lowercase
                    coords = COUNTRY_COORDS.get(entity_name.lower())
                if not coords:
                    continue

                lat, lon = coords
                level = alert.get("level", "warning")
                severity = "critical" if level in ("critical", "severe") else "high" if level == "warning" else "medium"

                results.append({
                    "name": f"Internet Outage: {entity_name}",
                    "latitude": lat,
                    "longitude": lon,
                    "country": entity_name,
                    "country_code": entity_code,
                    "entity_type": entity_type,
                    "severity": severity,
                    "level": level,
                    "datasource": alert.get("datasource", ""),
                    "date": alert.get("time", ""),
                    "score": alert.get("score", 0),
                    "source": "IODA",
                    "description": alert.get("description", ""),
                })

            logger.info("IODA: %d internet outage alerts", len(results))
        except httpx.HTTPError as exc:
            logger.warning("IODA fetch failed: %s", exc)
        return results

    async def _fetch_ioda_events(self, client: httpx.AsyncClient) -> List[dict]:
        """Alternative: fetch IODA outage events for monitored countries."""
        results: List[dict] = []
        try:
            import time
            now = int(time.time())
            day_ago = now - 86400

            resp = await client.get(
                f"{_IODA_BASE}/outages/events",
                params={
                    "from": str(day_ago),
                    "until": str(now),
                    "entityType": "country",
                    "limit": 200,
                },
                timeout=_IODA_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            signals = data if isinstance(data, list) else data.get("data", [])

            for signal in signals:
                entity_code = signal.get("entity", {}).get("code", "")
                if entity_code not in _MONITORED_COUNTRIES:
                    continue

                entity_name = signal.get("entity", {}).get("name", entity_code)
                coords = COUNTRY_COORDS.get(entity_code) or COUNTRY_COORDS.get(entity_name)
                if not coords:
                    continue

                # Check if there's a significant drop
                value = signal.get("value", 100)
                baseline = signal.get("baseline", 100)
                if baseline > 0 and value < baseline * 0.7:
                    severity = "critical" if value < baseline * 0.3 else "high"
                    pct_drop = round((1 - value / baseline) * 100)

                    results.append({
                        "name": f"Internet Drop: {entity_name} (-{pct_drop}%)",
                        "latitude": coords[0],
                        "longitude": coords[1],
                        "country": entity_name,
                        "country_code": entity_code,
                        "entity_type": "country",
                        "severity": severity,
                        "level": "outage",
                        "datasource": signal.get("datasource", ""),
                        "date": signal.get("time", ""),
                        "score": pct_drop,
                        "source": "IODA",
                        "description": f"{pct_drop}% drop in internet connectivity",
                    })

            logger.info("IODA signals: %d significant drops", len(results))
        except httpx.HTTPError as exc:
            logger.debug("IODA signals failed: %s", exc)
        return results

    async def _fetch_gdelt_outages(self, client: httpx.AsyncClient) -> List[dict]:
        """Fallback: mine GDELT for internet shutdown/blackout news."""
        results: List[dict] = []
        queries = [
            "internet shutdown OR internet blackout OR network outage",
            "internet cut off OR communications blackout OR telecom disruption",
        ]

        for query in queries:
            try:
                features = await self._gdelt(client, query, timespan="3D", maxrows=100)
                for feat in features:
                    props = feat.get("properties", {}) if isinstance(feat, dict) else {}
                    geom = feat.get("geometry", {})
                    coords = geom.get("coordinates", [None, None])

                    if coords[0] is None or coords[1] is None:
                        continue

                    title = props.get("name", props.get("title", "Internet Outage"))
                    title_lower = title.lower()

                    # Severity inference
                    if any(w in title_lower for w in ["blackout", "shut down", "total", "nationwide"]):
                        severity = "critical"
                    elif any(w in title_lower for w in ["disruption", "partial", "degraded"]):
                        severity = "high"
                    else:
                        severity = "medium"

                    results.append({
                        "name": title[:200],
                        "latitude": coords[1],
                        "longitude": coords[0],
                        "country": props.get("country", ""),
                        "country_code": "",
                        "entity_type": "country",
                        "severity": severity,
                        "level": "reported",
                        "datasource": "news",
                        "date": props.get("date", ""),
                        "score": 0,
                        "source": props.get("source", "GDELT"),
                        "description": title,
                    })
            except Exception as exc:
                logger.debug("GDELT outage query failed: %s", exc)

        logger.info("GDELT internet outages: %d reports", len(results))
        return results
