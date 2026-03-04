"""Military base location fetcher (Overpass + Wikidata + hardcoded strategic bases)."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

# Fixed Overpass: search node, way, AND relation for military facilities
# Also include landuse=military and aeroway=aerodrome with military
_OVERPASS_QUERY = (
    '[out:json][timeout:120];'
    '('
    'node["military"~"airfield|barracks|naval_base|base|range|training_area|bunker|checkpoint"];'
    'way["military"~"airfield|barracks|naval_base|base|range|training_area|bunker"];'
    'relation["military"~"airfield|barracks|naval_base|base|range|training_area"];'
    'node["landuse"="military"];'
    'way["landuse"="military"];'
    'node["aeroway"="aerodrome"]["military"="yes"];'
    'way["aeroway"="aerodrome"]["military"="yes"];'
    ');'
    'out center qt 3000;'
)

# Expanded Wikidata: military base + airbase + naval base + army base
_SPARQL = """
SELECT ?base ?baseLabel ?lat ?lon ?countryLabel ?operatorLabel WHERE {
  {?base wdt:P31/wdt:P279* wd:Q18691599.}   # military base (+ subclasses)
  UNION {?base wdt:P31 wd:Q245016.}          # military airfield
  UNION {?base wdt:P31 wd:Q1785116.}         # naval base
  UNION {?base wdt:P31 wd:Q15303838.}        # military installation
  UNION {?base wdt:P31 wd:Q4200568.}         # air force base
  ?base wdt:P625 ?coord .
  OPTIONAL { ?base wdt:P17 ?country . }
  OPTIONAL { ?base wdt:P137 ?operator . }
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 2000
"""

# Strategic military bases that MUST appear (hardcoded as fallback)
_STRATEGIC_BASES = [
    # US Major Bases
    ("Camp Humphreys", "South Korea", "US Army", 36.96, 127.03, "base"),
    ("Ramstein Air Base", "Germany", "USAF", 49.44, 7.60, "airfield"),
    ("Naval Station Norfolk", "United States", "US Navy", 36.95, -76.33, "naval_base"),
    ("Diego Garcia", "British Indian Ocean Territory", "US Navy/RAF", -7.32, 72.42, "naval_base"),
    ("Al Udeid Air Base", "Qatar", "USAF", 25.12, 51.31, "airfield"),
    ("Kadena Air Base", "Japan", "USAF", 26.35, 127.77, "airfield"),
    ("Naval Base Guam", "Guam", "US Navy", 13.44, 144.65, "naval_base"),
    ("Incirlik Air Base", "Turkey", "USAF/Turkish AF", 37.00, 35.43, "airfield"),
    ("Naval Station Rota", "Spain", "US Navy", 36.64, -6.35, "naval_base"),
    ("RAF Lakenheath", "United Kingdom", "USAF", 52.41, 0.56, "airfield"),
    ("Fort Liberty (Bragg)", "United States", "US Army", 35.14, -79.00, "base"),
    ("Pearl Harbor", "United States", "US Navy", 21.35, -157.97, "naval_base"),
    ("Yokosuka Naval Base", "Japan", "US Navy", 35.28, 139.67, "naval_base"),
    ("Bagram Air Base", "Afghanistan", "US/Afghan", 34.95, 69.27, "airfield"),
    ("Thule Air Base", "Greenland", "US Space Force", 76.53, -68.70, "airfield"),
    # Russia
    ("Sevastopol Naval Base", "Crimea/Ukraine", "Russian Navy", 44.62, 33.53, "naval_base"),
    ("Kaliningrad", "Russia", "Russian Military", 54.71, 20.51, "base"),
    ("Tartus Naval Base", "Syria", "Russian Navy", 34.89, 35.89, "naval_base"),
    ("Khmeimim Air Base", "Syria", "Russian AF", 35.41, 35.95, "airfield"),
    ("Vladivostok Naval Base", "Russia", "Pacific Fleet", 43.12, 131.88, "naval_base"),
    ("Murmansk Naval Base", "Russia", "Northern Fleet", 68.97, 33.09, "naval_base"),
    # China
    ("Djibouti Support Base", "Djibouti", "PLA Navy", 11.59, 43.15, "naval_base"),
    ("Yulin Naval Base", "China", "PLA Navy", 18.23, 109.57, "naval_base"),
    ("Woody Island", "South China Sea", "PLA", 16.84, 112.34, "base"),
    ("Fiery Cross Reef", "South China Sea", "PLA", 9.55, 112.89, "base"),
    # Iran
    ("Bandar Abbas Naval Base", "Iran", "IRIN", 27.15, 56.28, "naval_base"),
    ("Isfahan Air Base", "Iran", "IRIAF", 32.75, 51.86, "airfield"),
    ("Parchin Military Complex", "Iran", "IRGC", 35.52, 51.77, "base"),
    ("Natanz Nuclear Facility", "Iran", "AEOI", 33.72, 51.73, "base"),
    ("Bushehr Naval Base", "Iran", "IRIN", 28.93, 50.84, "naval_base"),
    ("Chabahar Naval Base", "Iran", "IRIN", 25.30, 60.62, "naval_base"),
    # Other
    ("Camp Lemonnier", "Djibouti", "US AFRICOM", 11.55, 43.16, "base"),
    ("Changi Naval Base", "Singapore", "RSN", 1.33, 104.00, "naval_base"),
    ("HMAS Stirling", "Australia", "RAN", -32.24, 115.69, "naval_base"),
    ("Devonport Naval Base", "United Kingdom", "Royal Navy", 50.38, -4.18, "naval_base"),
    ("Toulon Naval Base", "France", "French Navy", 43.10, 5.93, "naval_base"),
]


class MilitaryBaseFetcher(BaseFetcher):
    """Fetches military base locations from Overpass + Wikidata + strategic database."""

    async def _from_overpass(self, client: httpx.AsyncClient) -> List[dict]:
        elements = await self._overpass(client, _OVERPASS_QUERY)
        results: List[dict] = []
        for el in elements:
            # For ways/relations, use center coordinates
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            tags = el.get("tags") or {}
            results.append({
                "name": tags.get("name", tags.get("official_name", "Military Installation")),
                "country": tags.get("addr:country", ""),
                "operator": tags.get("operator", ""),
                "latitude": lat, "longitude": lon,
                "type": tags.get("military", tags.get("landuse", "base")),
                "branch": tags.get("operator", ""), "status": "active",
            })
        return results

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        bindings = await self._wikidata(client, _SPARQL)
        results: List[dict] = []
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            results.append({
                "name": self._label(b, "baseLabel", "Military Base"),
                "country": self._label(b, "countryLabel"),
                "operator": self._label(b, "operatorLabel"),
                "latitude": coords[0], "longitude": coords[1],
                "type": "base", "branch": "", "status": "active",
            })
        return results

    async def _from_strategic_db(self, client: httpx.AsyncClient) -> List[dict]:
        """Always-available strategic base database."""
        return [
            {
                "name": name, "country": country, "operator": op,
                "latitude": lat, "longitude": lon,
                "type": btype, "branch": op, "status": "active",
            }
            for name, country, op, lat, lon, btype in _STRATEGIC_BASES
        ]

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._collect(
            client, self._from_overpass, self._from_wikidata, self._from_strategic_db,
        )
