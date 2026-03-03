"""Breaking news feed fetcher with RSS primary and GDELT fallback."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import List

import httpx

from .base import BaseFetcher
from ..utils import COUNTRY_COORDS

logger = logging.getLogger("agus.fetchers")

_RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "http://feeds.reuters.com/Reuters/worldNews",
]

_FEED_NAMES = {
    "bbci.co.uk": "BBC",
    "aljazeera.com": "Al Jazeera",
    "reuters.com": "Reuters",
}

# Only full country names (3+ chars) to avoid false positives from ISO codes
_COUNTRY_NAMES = sorted(
    (k for k in COUNTRY_COORDS if len(k) > 2),
    key=len, reverse=True,
)


def _geocode_title(title: str):
    """Find first country name in title, return (name, lat, lon) or None."""
    title_lower = title.lower()
    for name in _COUNTRY_NAMES:
        if name.lower() in title_lower:
            lat, lon = COUNTRY_COORDS[name]
            return name, lat, lon
    return None


def _source_name(url: str) -> str:
    for domain, name in _FEED_NAMES.items():
        if domain in url:
            return name
    return "RSS"


class NewsFetcher(BaseFetcher):
    """Fetches breaking geolocated news from RSS feeds with GDELT fallback."""

    @staticmethod
    def _parse_html_articles(html: str) -> List[dict]:
        return [
            {"url": m.group(1), "title": m.group(2)}
            for m in re.finditer(r'href="([^"]+)"[^>]*title="([^"]*)"', html or "")
        ]

    async def _from_rss(self, client: httpx.AsyncClient) -> List[dict]:
        features: List[dict] = []
        for feed_url in _RSS_FEEDS:
            source = _source_name(feed_url)
            try:
                resp = await client.get(feed_url, timeout=15.0)
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
                for item in root.iter("item"):
                    title_el = item.find("title")
                    if title_el is None or title_el.text is None:
                        continue
                    title = title_el.text.strip()
                    geo = _geocode_title(title)
                    if not geo:
                        continue
                    country, lat, lon = geo
                    link_el = item.find("link")
                    pub_el = item.find("pubDate")
                    desc_el = item.find("description")
                    link = link_el.text.strip() if link_el is not None and link_el.text else ""
                    pub_date = pub_el.text.strip() if pub_el is not None and pub_el.text else ""
                    description = ""
                    if desc_el is not None and desc_el.text:
                        description = desc_el.text.strip()[:300]
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        "properties": {
                            "name": title,
                            "title": title,
                            "url": link,
                            "source": source,
                            "country": country,
                            "pubDate": pub_date,
                            "description": description,
                        },
                    })
            except Exception as exc:
                logger.warning("RSS feed %s failed: %s", feed_url, exc)
        return features

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        features = await self._gdelt(client, "sourcelang:english", "24H", 500)
        enriched = []
        for feat in features:
            props = feat.get("properties") or {}
            coords = (feat.get("geometry") or {}).get("coordinates") or [0, 0]
            if coords[0] == 0 and coords[1] == 0:
                continue
            articles = self._parse_html_articles(props.get("html", ""))
            if articles:
                props["title"] = articles[0]["title"]
                props["url"] = articles[0]["url"]
                props["source"] = "GDELT"
                props["country"] = props.get("name", "Unknown")
                props["article_count"] = props.get("count", 0)
                if len(articles) > 1:
                    props["more_headlines"] = " | ".join(
                        a["title"][:60] for a in articles[1:4]
                    )
                enriched.append(feat)
        return enriched

    async def fetch(self, client: httpx.AsyncClient) -> dict:
        features = await self._try_sources(client, self._from_rss, self._from_gdelt)
        return {"type": "FeatureCollection", "features": features or []}
