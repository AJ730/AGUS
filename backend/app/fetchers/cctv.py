"""CCTV/webcam camera fetcher (Overpass batched city queries + static fallback)."""

from __future__ import annotations

import logging
from typing import List, Tuple

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

# City-center bboxes — 4 cities per Overpass batch query (tested sweet spot)
# Interleaved by continent so each batch of 4 covers the globe
_CITIES: List[Tuple[str, float, float, float, float]] = [
    # Batch 1: Americas + Europe + Asia + Oceania
    ("New York",      40.72, -74.01, 40.79, -73.94),
    ("London",        51.48, -0.15,  51.55,  0.05),
    ("Tokyo",         35.65, 139.70, 35.72, 139.78),
    ("Sydney",       -33.88, 151.18, -33.85, 151.23),
    # Batch 2
    ("Paris",         48.83,  2.28,  48.89,  2.40),
    ("Los Angeles",   33.98, -118.30, 34.06, -118.22),
    ("Beijing",       39.90, 116.37, 39.95, 116.42),
    ("Sao Paulo",    -23.57, -46.67, -23.53, -46.62),
    # Batch 3
    ("Berlin",        52.48, 13.34,  52.55, 13.44),
    ("Seoul",         37.54, 126.96, 37.58, 127.02),
    ("Chicago",       41.85, -87.67, 41.92, -87.60),
    ("Dubai",         25.17, 55.25,  25.23, 55.31),
    # Batch 4
    ("Moscow",        55.72, 37.57,  55.79, 37.67),
    ("Singapore",      1.28, 103.83,  1.32, 103.87),
    ("Washington DC", 38.88, -77.05, 38.92, -77.00),
    ("Cairo",         30.03, 31.22,  30.07, 31.27),
    # Batch 5
    ("Rome",          41.88, 12.46,  41.92, 12.52),
    ("Mumbai",        19.05, 72.86,  19.10, 72.92),
    ("Toronto",       43.63, -79.42, 43.68, -79.36),
    ("Istanbul",      41.00, 28.96,  41.04, 29.01),
    # Batch 6
    ("Shanghai",      31.21, 121.44, 31.26, 121.50),
    ("Madrid",        40.40, -3.72,  40.44, -3.67),
    ("Mexico City",   19.40, -99.18, 19.45, -99.12),
    ("Cape Town",    -33.94, 18.40, -33.90, 18.45),
    # Batch 7
    ("Amsterdam",     52.35,  4.87,  52.39,  4.93),
    ("Hong Kong",     22.28, 114.14, 22.32, 114.20),
    ("San Francisco", 37.76, -122.44, 37.80, -122.39),
    ("Nairobi",       -1.30, 36.80,  -1.26, 36.84),
    # Batch 8
    ("Bangkok",       13.73, 100.50, 13.77, 100.55),
    ("Prague",        50.07, 14.40,  50.10, 14.45),
    ("Buenos Aires", -34.62, -58.40, -34.58, -58.35),
    ("Delhi",         28.61, 77.20,  28.66, 77.25),
    # Batch 9
    ("Vienna",        48.19, 16.35,  48.23, 16.40),
    ("Taipei",        25.02, 121.51, 25.06, 121.56),
    ("Bogota",         4.60, -74.10,   4.65, -74.05),
    ("Tel Aviv",      32.06, 34.76,  32.10, 34.80),
    # Batch 10
    ("Stockholm",     59.32, 18.04,  59.35, 18.10),
    ("Warsaw",        52.22, 20.98,  52.26, 21.03),
    ("Brussels",      50.83,  4.33,  50.87,  4.38),
    ("Melbourne",    -37.83, 144.95, -37.79, 145.00),
]

# Rotate which batch we query each refresh cycle to build global coverage
_BATCH_SIZE = 4
_PER_CITY_LIMIT = 150
_TIMEOUT = httpx.Timeout(connect=10.0, read=45.0, write=5.0, pool=10.0)
_OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Module-level state: accumulated cameras + rotation index
_accumulated: List[dict] = []
_batch_index: int = 0



class CCTVFetcher(BaseFetcher):
    """Fetches surveillance cameras from Overpass — one batch per refresh cycle."""

    @staticmethod
    def _build_query(cities: list) -> str:
        union = "".join(
            f'node["man_made"="surveillance"]({s},{w},{n},{e});'
            for _, s, w, n, e in cities
        )
        limit = _PER_CITY_LIMIT * len(cities)
        return f'[out:json][timeout:40];({union});out body qt {limit};'

    @staticmethod
    def _parse(elements: list, city_bboxes: list) -> List[dict]:
        results: List[dict] = []
        for el in elements:
            lat, lon = el.get("lat"), el.get("lon")
            if lat is None or lon is None:
                continue
            city = "Unknown"
            for name, s, w, n, e in city_bboxes:
                if s <= lat <= n and w <= lon <= e:
                    city = name
                    break
            tags = el.get("tags") or {}
            results.append({
                "name": tags.get("name", tags.get("operator", "Camera")),
                "city": city,
                "country": tags.get("addr:country", ""),
                "latitude": lat, "longitude": lon,
                "type": tags.get("surveillance:type", "surveillance"),
                "operator": tags.get("operator", ""),
                "stream_url": tags.get("contact:webcam", tags.get("url", "")),
                "source": "OpenStreetMap",
            })
        return results

    async def _fetch_batch(self, cities: list) -> List[dict]:
        """Fetch one batch using a dedicated client (avoids shared pool)."""
        query = self._build_query(cities)
        names = [c[0] for c in cities]
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for url in _OVERPASS_URLS:
                try:
                    resp = await client.post(url, data={"data": query},
                                             timeout=_TIMEOUT)
                    if resp.status_code in (429, 504):
                        logger.warning("CCTV [%s]: %d from %s",
                                       ", ".join(names), resp.status_code,
                                       url.split("/")[2])
                        continue
                    resp.raise_for_status()
                    elements = resp.json().get("elements") or []
                    results = self._parse(elements, cities)
                    logger.info("CCTV [%s]: %d cameras",
                                ", ".join(names), len(results))
                    return results
                except Exception as exc:
                    logger.warning("CCTV [%s]: %s on %s",
                                   ", ".join(names), exc,
                                   url.split("/")[2])
                    continue
        logger.warning("CCTV [%s]: all mirrors failed", ", ".join(names))
        return []

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        global _accumulated, _batch_index

        # Split all cities into batches of 4
        all_batches = [
            _CITIES[i:i + _BATCH_SIZE]
            for i in range(0, len(_CITIES), _BATCH_SIZE)
        ]

        # Fetch ONE batch this cycle (fast — no sleeps, ~3-5 seconds)
        batch = all_batches[_batch_index % len(all_batches)]
        new_cameras = await self._fetch_batch(batch)

        # Deduplicate by (lat, lon) and merge into accumulated set
        existing = {(c["latitude"], c["longitude"]) for c in _accumulated}
        for cam in new_cameras:
            key = (cam["latitude"], cam["longitude"])
            if key not in existing:
                _accumulated.append(cam)
                existing.add(key)

        _batch_index += 1

        logger.info("CCTV total: %d cameras (batch %d/%d)",
                     len(_accumulated), _batch_index, len(all_batches))
        return list(_accumulated)
