"""Geolocated news events fetcher with RSS primary and GDELT fallback."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import List

import httpx

from .base import BaseFetcher
from ..utils import COUNTRY_COORDS

logger = logging.getLogger("agus.fetchers")

_RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
]

# Pre-filter: only match full country names (3+ chars) to avoid false positives
_COUNTRY_NAMES = sorted(
    (k for k in COUNTRY_COORDS if len(k) > 2),
    key=len, reverse=True,
)


def _geocode_title(title: str) -> tuple | None:
    """Find first country name in title, return (name, lat, lon) or None."""
    title_lower = title.lower()
    for name in _COUNTRY_NAMES:
        if name.lower() in title_lower:
            lat, lon = COUNTRY_COORDS[name]
            return name, lat, lon
    return None


class EventFetcher(BaseFetcher):
    """Fetches geolocated news events from RSS feeds with GDELT fallback."""

    async def _from_rss(self, client: httpx.AsyncClient) -> List[dict]:
        features: List[dict] = []
        for url in _RSS_FEEDS:
            try:
                resp = await client.get(url, timeout=15.0)
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
                for item in root.iter("item"):
                    title_el = item.find("title")
                    desc_el = item.find("description")
                    if title_el is None or title_el.text is None:
                        continue
                    title = title_el.text.strip()
                    geo = _geocode_title(title)
                    if not geo:
                        continue
                    country, lat, lon = geo
                    description = ""
                    if desc_el is not None and desc_el.text:
                        description = desc_el.text.strip()[:300]
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        "properties": {
                            "name": title,
                            "description": description,
                            "country": country,
                            "source": "RSS",
                        },
                    })
            except Exception as exc:
                logger.warning("RSS feed %s failed: %s", url, exc)
        return features

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        query = "(conflict OR military OR protest)"
        return await self._gdelt(client, query, "24H", 500)

    async def fetch(self, client: httpx.AsyncClient) -> dict:
        features = await self._try_sources(client, self._from_rss, self._from_gdelt)
        return {"type": "FeatureCollection", "features": features or []}
