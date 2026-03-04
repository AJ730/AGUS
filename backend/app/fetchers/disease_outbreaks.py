"""Disease outbreak fetcher — WHO DON + disease.sh.

Fetches active disease outbreaks by country.
Free, no authentication required.
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from ..utils import COUNTRY_COORDS
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_WHO_URL = "https://www.who.int/api/news/diseaseoutbreaknews"
_DISEASE_SH_URL = "https://disease.sh/v3/covid-19"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)


class DiseaseOutbreakFetcher(BaseFetcher):
    """Fetches disease outbreak data from WHO DON API and disease.sh."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch disease outbreaks from WHO + disease.sh."""
        return await self._collect(
            client,
            self._fetch_who_don,
            self._fetch_disease_sh,
        )

    async def _fetch_who_don(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch WHO Disease Outbreak News."""
        results: List[dict] = []
        try:
            resp = await client.get(
                _WHO_URL,
                params={"$orderby": "PublicationDate desc", "$top": 50},
                timeout=_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("value") or data if isinstance(data, list) else []
            if isinstance(data, dict):
                items = data.get("value", [])

            for item in items[:30]:
                title = item.get("Title") or item.get("OverrideTitle") or "Disease Outbreak"
                summary = item.get("Summary") or ""

                # Extract country from title (format: "Disease - Country")
                country_name = ""
                if " - " in title:
                    parts = title.split(" - ")
                    country_name = parts[-1].strip()
                elif " in " in title.lower():
                    country_name = title.lower().split(" in ")[-1].strip().title()

                # Geocode from country name or title keywords
                lat, lon = self._geocode_country(country_name)
                if lat is None:
                    # Try geocoding from full title
                    lat, lon = self._geocode_country(title)
                if lat is None:
                    continue

                date = item.get("PublicationDate") or ""
                severity = "High" if any(
                    w in title.lower()
                    for w in ["ebola", "marburg", "plague", "cholera", "mpox", "avian"]
                ) else "Medium"

                results.append({
                    "name": title[:120],
                    "latitude": lat,
                    "longitude": lon,
                    "country": country_name,
                    "disease": self._extract_disease(title),
                    "severity": severity,
                    "date": str(date)[:10],
                    "source": "WHO DON",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("WHO DON fetch failed: %s", exc)
        return results

    async def _fetch_disease_sh(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch current pandemic/epidemic data from disease.sh."""
        results: List[dict] = []
        try:
            # Fetch countries with active outbreaks of various diseases
            resp = await client.get(
                f"{_DISEASE_SH_URL}/countries",
                params={"sort": "todayCases"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            countries = resp.json()

            for c in countries[:30]:
                cases_today = c.get("todayCases", 0) or 0
                if cases_today < 100:
                    continue
                info = c.get("countryInfo", {})
                lat = info.get("lat")
                lon = info.get("long")
                if lat is None or lon is None:
                    continue

                results.append({
                    "name": f"COVID-19 — {c.get('country', 'Unknown')}",
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "country": c.get("country", ""),
                    "disease": "COVID-19",
                    "severity": (
                        "Critical" if cases_today > 10000
                        else "High" if cases_today > 1000
                        else "Medium"
                    ),
                    "cases_today": cases_today,
                    "deaths_today": c.get("todayDeaths", 0),
                    "active": c.get("active", 0),
                    "source": "disease.sh",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("disease.sh fetch failed: %s", exc)
        return results

    @staticmethod
    def _geocode_country(country_name: str):
        """Look up country coords from COUNTRY_COORDS."""
        if not country_name:
            return None, None
        name_lower = country_name.lower().strip()
        for name, (lat, lon) in COUNTRY_COORDS.items():
            if name.lower() == name_lower:
                return lat, lon
            # Partial match
            if name_lower in name.lower() or name.lower() in name_lower:
                return lat, lon
        return None, None

    @staticmethod
    def _extract_disease(title: str) -> str:
        """Extract disease name from WHO DON title."""
        diseases = [
            "Ebola", "Marburg", "Cholera", "Plague", "Mpox", "COVID-19",
            "Avian Influenza", "Yellow Fever", "Dengue", "Measles", "Diphtheria",
            "Polio", "Meningitis", "Hepatitis", "Lassa Fever", "Nipah",
        ]
        title_lower = title.lower()
        for d in diseases:
            if d.lower() in title_lower:
                return d
        return "Outbreak"
