"""Telegram-style OSINT feed fetcher — aggregates OSINT channels via multiple RSS sources."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Tuple

import httpx

from ..utils import COUNTRY_COORDS
from .base import BaseFetcher
from .conflict_zones import CONFLICT_ZONES as _CONFLICT_ZONES

logger = logging.getLogger("agus.fetchers")

# OSINT RSS feeds (direct feeds that don't need bridges)
_OSINT_RSS_FEEDS = [
    # --- OSINT aggregators ---
    ("https://liveuamap.com/rss", "LiveUAMap", "conflict"),
    ("https://www.understandingwar.org/feed", "Understanding War", "conflict"),
    ("https://www.bellingcat.com/feed/", "Bellingcat", "conflict"),
    ("https://acleddata.com/feed/", "ACLED", "conflict"),
    # --- Breaking news (global) ---
    ("https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera", "breaking"),
    ("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World", "breaking"),
    ("https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "NYT World", "breaking"),
    ("https://feeds.washingtonpost.com/rss/world", "WaPo World", "breaking"),
    ("https://feeds.reuters.com/Reuters/worldNews", "Reuters", "breaking"),
    ("https://www.theguardian.com/world/rss", "Guardian World", "breaking"),
    # --- Defense / military ---
    ("https://news.usni.org/feed", "USNI News", "military"),
    ("https://www.navalnews.com/feed/", "Naval News", "military"),
    ("https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml", "Defense News", "military"),
    ("https://www.janes.com/feeds/news", "Janes", "military"),
    ("https://www.thedefensepost.com/feed/", "Defense Post", "conflict"),
    ("https://www.thedrive.com/the-war-zone/feed", "War Zone", "military"),
    ("https://breakingdefense.com/feed/", "Breaking Defense", "military"),
    ("https://www.airforcetimes.com/arc/outboundfeeds/rss/?outputType=xml", "AF Times", "military"),
    ("https://www.militarytimes.com/arc/outboundfeeds/rss/?outputType=xml", "Military Times", "military"),
    # --- Geopolitics / analysis ---
    ("https://www.crisisgroup.org/latest-updates/feed", "Crisis Group", "geopolitics"),
    ("https://www.foreignaffairs.com/rss.xml", "Foreign Affairs", "geopolitics"),
    ("https://warontherocks.com/feed/", "War on the Rocks", "geopolitics"),
    ("https://www.chathamhouse.org/rss/research", "Chatham House", "geopolitics"),
    ("https://carnegieendowment.org/rss/solr", "Carnegie", "geopolitics"),
    # --- Humanitarian ---
    ("https://reliefweb.int/updates/rss.xml", "ReliefWeb", "humanitarian"),
    # --- Middle East ---
    ("https://www.middleeasteye.net/rss", "Middle East Eye", "conflict"),
    ("https://www.timesofisrael.com/feed/", "Times of Israel", "conflict"),
    ("https://english.alarabiya.net/tools/rss", "Al Arabiya", "breaking"),
    ("https://english.aawsat.com/feed", "Asharq Al-Awsat", "breaking"),
    # --- Iran ---
    ("https://www.iranintl.com/en/feed", "Iran International", "conflict"),
    ("https://en.irna.ir/rss", "IRNA English", "geopolitics"),
    ("https://www.tehrantimes.com/rss", "Tehran Times", "geopolitics"),
    ("https://www.presstv.ir/RSS", "PressTV", "geopolitics"),
    # --- Ukraine / Russia ---
    ("https://www.pravda.com.ua/eng/rss/", "Ukrayinska Pravda", "conflict"),
    ("https://www.kyivindependent.com/feed/", "Kyiv Independent", "conflict"),
    ("https://www.themoscowtimes.com/rss/news", "Moscow Times", "geopolitics"),
    # --- Africa ---
    ("https://www.africanews.com/feed/", "Africanews", "breaking"),
    ("https://issafrica.org/iss-today/feed", "ISS Africa", "conflict"),
    # --- Asia-Pacific ---
    ("https://www.scmp.com/rss/91/feed", "SCMP Asia", "geopolitics"),
    ("https://thediplomat.com/feed/", "The Diplomat", "geopolitics"),
    ("https://www.nknews.org/feed/", "NK News", "geopolitics"),
    # --- Cyber / intelligence ---
    ("https://krebsonsecurity.com/feed/", "Krebs on Security", "cyber"),
    ("https://www.schneier.com/feed/", "Schneier", "cyber"),
    ("https://therecord.media/feed/", "The Record", "cyber"),
    ("https://www.darkreading.com/rss.xml", "Dark Reading", "cyber"),
    # --- Maritime ---
    ("https://gcaptain.com/feed/", "gCaptain", "maritime"),
    ("https://splash247.com/feed/", "Splash 247", "maritime"),
]

# Build sorted country list for title geocoding (longest first)
_REGION_KEYWORDS = sorted(
    ((k, v) for k, v in COUNTRY_COORDS.items() if len(k) > 2),
    key=lambda x: -len(x[0]),
)


def _geocode_headline(title: str) -> Tuple[float, float, str] | None:
    """Try to extract coordinates from a headline by matching location names."""
    title_lower = title.lower()

    # Check conflict zone keywords first (more specific)
    for zone, (lat, lon) in sorted(_CONFLICT_ZONES.items(), key=lambda x: -len(x[0])):
        if zone in title_lower:
            return lat, lon, zone.title()

    # Check country names
    for name, coords in _REGION_KEYWORDS:
        if name.lower() in title_lower:
            return coords[0], coords[1], name

    return None


def _parse_rss(xml_text: str) -> List[dict]:
    """Parse RSS XML into list of {title, link, pubDate}."""
    items = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            desc = (item.findtext("description") or "").strip()
            if title:
                items.append({
                    "title": title,
                    "link": link,
                    "date": pub,
                    "description": re.sub(r'<[^>]+>', '', desc)[:300],
                })
        # Also try Atom format
        if not items:
            ns = "{http://www.w3.org/2005/Atom}"
            for entry in root.iter(f"{ns}entry"):
                title = (entry.findtext(f"{ns}title") or "").strip()
                link_el = entry.find(f"{ns}link")
                link = link_el.get("href", "") if link_el is not None else ""
                pub = (entry.findtext(f"{ns}published") or entry.findtext(f"{ns}updated") or "").strip()
                if title:
                    items.append({"title": title, "link": link, "date": pub, "description": ""})
    except ET.ParseError:
        pass
    return items


class TelegramOSINTFetcher(BaseFetcher):
    """Fetches and geolocates OSINT from public RSS feeds (defense, conflict, geopolitics)."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        results: List[dict] = []
        seen_titles: set = set()

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=20.0, write=5.0, pool=10.0),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        ) as rss_client:
            for url, label, category in _OSINT_RSS_FEEDS:
                try:
                    resp = await rss_client.get(url)
                    if resp.status_code != 200:
                        continue
                    items = _parse_rss(resp.text)
                    for item in items[:20]:
                        title = item["title"]
                        # Dedup
                        title_key = re.sub(r'\s+', ' ', title.lower().strip())[:80]
                        if title_key in seen_titles:
                            continue
                        seen_titles.add(title_key)

                        # Try title first, then description
                        geo = _geocode_headline(title)
                        if not geo:
                            geo = _geocode_headline(item.get("description", ""))
                        if not geo:
                            continue

                        lat, lon, location = geo
                        severity = "high" if category == "conflict" else "medium"

                        results.append({
                            "title": title[:200],
                            "latitude": lat,
                            "longitude": lon,
                            "location": location,
                            "channel": label,
                            "category": category,
                            "severity": severity,
                            "date": item.get("date", ""),
                            "url": item.get("link", ""),
                            "source": label,
                            "type": "telegram_osint",
                        })
                except Exception as exc:
                    logger.debug("OSINT RSS %s: %s", label, exc)
                    continue

        logger.info("OSINT feeds: %d geolocated items from %d feeds",
                     len(results), len(_OSINT_RSS_FEEDS))
        return results
