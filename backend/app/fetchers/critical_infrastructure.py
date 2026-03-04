"""Critical infrastructure fetcher — Overpass API.

Fetches power plants, substations, pipelines, dams, refineries from OSM.
Free, no authentication required.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=5.0, pool=10.0)
_OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Queries for different infrastructure types
_QUERIES = {
    "power_plant": '[out:json][timeout:45];node["power"="plant"];out body 500;',
    "dam": '[out:json][timeout:45];(node["waterway"="dam"];way["waterway"="dam"];);out center 200;',
    "oil_refinery": '[out:json][timeout:45];(node["man_made"="petroleum_well"];node["industrial"="refinery"];);out body 200;',
}

# Module-level accumulated results + rotation index
_accumulated: List[dict] = []
_query_index: int = 0


class CriticalInfrastructureFetcher(BaseFetcher):
    """Fetches critical infrastructure from OpenStreetMap via Overpass."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch one infrastructure type per cycle, accumulate over time."""
        global _accumulated, _query_index

        query_keys = list(_QUERIES.keys())
        key = query_keys[_query_index % len(query_keys)]
        query = _QUERIES[key]

        new_items = await self._fetch_overpass(key, query)

        # Deduplicate by (lat, lon) and merge
        existing = {(r["latitude"], r["longitude"]) for r in _accumulated}
        for item in new_items:
            coord_key = (item["latitude"], item["longitude"])
            if coord_key not in existing:
                _accumulated.append(item)
                existing.add(coord_key)

        _query_index += 1
        logger.info("Infrastructure total: %d items (fetched %s: %d new)",
                     len(_accumulated), key, len(new_items))
        return list(_accumulated)

    async def _fetch_overpass(self, infra_type: str, query: str) -> List[dict]:
        """Fetch from Overpass with mirror failover."""
        async with httpx.AsyncClient(follow_redirects=True) as oc:
            for url in _OVERPASS_URLS:
                try:
                    resp = await oc.post(url, data={"data": query}, timeout=_TIMEOUT)
                    if resp.status_code in (429, 504):
                        logger.warning("Infrastructure [%s]: %d from %s",
                                       infra_type, resp.status_code, url.split("/")[2])
                        continue
                    resp.raise_for_status()
                    elements = resp.json().get("elements", [])
                    return self._parse(elements, infra_type)
                except Exception as exc:
                    logger.warning("Infrastructure [%s]: %s on %s",
                                   infra_type, exc, url.split("/")[2])
                    continue
        return []

    @staticmethod
    def _parse(elements: list, infra_type: str) -> List[dict]:
        """Parse Overpass elements into standardized dicts."""
        results: List[dict] = []
        type_labels = {
            "power_plant": "Power Plant",
            "dam": "Dam",
            "oil_refinery": "Oil/Gas Facility",
        }
        for el in elements:
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            tags = el.get("tags") or {}
            name = tags.get("name", tags.get("operator", type_labels.get(infra_type, "Infrastructure")))

            # Determine capacity/output for power plants
            output_mw = tags.get("plant:output:electricity", tags.get("generator:output:electricity", ""))

            # Fuel/energy source
            fuel = tags.get("plant:source", tags.get("generator:source", tags.get("fuel", "")))

            results.append({
                "name": name,
                "latitude": float(lat),
                "longitude": float(lon),
                "infra_type": infra_type,
                "type_label": type_labels.get(infra_type, "Infrastructure"),
                "operator": tags.get("operator", ""),
                "output": output_mw,
                "fuel": fuel,
                "country": tags.get("addr:country", ""),
                "source": "OpenStreetMap",
            })
        return results
