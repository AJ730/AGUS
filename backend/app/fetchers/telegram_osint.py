"""Telegram-style OSINT feed fetcher — aggregates OSINT channels via multiple RSS sources."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import List, Tuple

import httpx

from ..utils import COUNTRY_COORDS
from .base import BaseFetcher

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

# Conflict zone keywords with approximate coordinates
_CONFLICT_ZONES = {
    "kherson": (46.6, 32.6), "zaporizhzhia": (47.8, 35.2),
    "donetsk": (48.0, 37.8), "luhansk": (48.6, 39.3),
    "bakhmut": (48.6, 38.0), "avdiivka": (48.1, 37.7),
    "kursk": (51.7, 36.2), "belgorod": (50.6, 36.6),
    "crimea": (45.0, 34.0), "sevastopol": (44.6, 33.5),
    "odesa": (46.5, 30.7), "kyiv": (50.4, 30.5),
    "kharkiv": (50.0, 36.2), "mariupol": (47.1, 37.5),
    "dnipro": (48.5, 35.0), "sumy": (50.9, 34.8),
    "mykolaiv": (46.97, 32.0), "pokrovsk": (48.3, 37.2),
    "gaza": (31.5, 34.47), "rafah": (31.3, 34.25),
    "khan younis": (31.35, 34.3), "jabalia": (31.54, 34.48),
    "nablus": (32.22, 35.25), "jenin": (32.46, 35.3),
    "tel aviv": (32.1, 34.8), "haifa": (32.8, 35.0),
    "beirut": (33.9, 35.5), "southern lebanon": (33.3, 35.4),
    "tyre": (33.27, 35.2), "baalbek": (34.0, 36.2),
    "homs": (34.7, 36.7), "aleppo": (36.2, 37.2),
    "idlib": (35.9, 36.6), "damascus": (33.5, 36.3),
    "khartoum": (15.6, 32.5), "darfur": (13.0, 25.0),
    "mogadishu": (2.0, 45.3), "taipei": (25.0, 121.5),
    "taiwan": (23.5, 121.0), "south china sea": (14.0, 115.0),
    "red sea": (19.0, 38.5), "houthi": (15.5, 43.5),
    "iran": (32.4, 53.7), "tehran": (35.7, 51.4),
    "isfahan": (32.65, 51.68), "strait of hormuz": (26.3, 56.8),
    "irgc": (35.7, 51.4), "natanz": (33.72, 51.73),
    "parchin": (35.24, 51.42), "semnan": (35.23, 53.92),
    "bandar abbas": (27.18, 56.28), "bushehr": (28.97, 50.84),
    "kharg island": (29.24, 50.33), "chabahar": (25.29, 60.64),
    "tabriz": (38.08, 46.30), "mashhad": (36.27, 59.61),
    "qom": (34.64, 50.88), "shiraz": (29.62, 52.53),
    "fordow": (34.88, 51.26), "arak": (34.09, 49.69),
    "yemen": (15.5, 48.5), "aden": (12.8, 45.0),
    "sanaa": (15.35, 44.2), "hodeidah": (14.8, 42.95),
    "kabul": (34.5, 69.2), "kandahar": (31.6, 65.7),
    "tigray": (13.5, 39.5), "ethiopia": (9.0, 38.7),
    "sudan": (15.6, 32.5), "chad": (12.1, 15.0),
    "sahel": (15.0, 2.0), "mali": (12.6, -8.0),
    "niger": (13.5, 2.1), "burkina faso": (12.4, -1.5),
    "myanmar": (19.75, 96.1), "mandalay": (21.97, 96.1),
    "yangon": (16.87, 96.2), "nagorno-karabakh": (39.8, 46.75),
    "congo": (-4.32, 15.32), "goma": (-1.68, 29.23),
    "north korea": (39.0, 125.75), "pyongyang": (39.0, 125.75),
    "west bank": (32.0, 35.2), "east jerusalem": (31.78, 35.23),
    "persian gulf": (26.0, 52.0), "arabian sea": (16.0, 63.0),
    "mediterranean": (35.5, 18.0), "black sea": (43.0, 33.0),
    "baltic sea": (56.5, 18.0), "arctic": (75.0, 30.0),
    # General conflict / military keywords
    "hezbollah": (33.9, 35.5), "hamas": (31.5, 34.47),
    "idf": (31.8, 34.8), "iron dome": (31.8, 34.8),
    "nato": (50.8, 4.4), "pentagon": (38.87, -77.06),
    "kremlin": (55.75, 37.62), "moscow": (55.75, 37.62),
    "beijing": (39.9, 116.4), "pyongyang": (39.0, 125.75),
    "houthi": (15.5, 43.5), "wagner": (15.6, 32.5),
    # Additional Iran military targets
    "iran nuclear": (32.65, 51.68), "iranian missile": (35.24, 51.42),
    "quds force": (35.7, 51.4), "khamenei": (35.7, 51.4),
    "esfahan": (32.65, 51.68), "hormuz": (26.3, 56.8),
    # Additional Ukraine targets
    "tokmak": (47.25, 35.7), "vuhledar": (47.78, 37.25),
    "chasiv yar": (48.6, 37.85), "kupiansk": (49.71, 37.61),
    "zaporizhzhia nuclear": (47.5, 34.6),
    # Additional Asia-Pacific
    "taiwan strait": (24.0, 119.5), "spratly": (10.0, 114.0),
    "paracel": (16.5, 112.0), "senkaku": (25.75, 123.47),
    # Additional Africa
    "mozambique": (-15.0, 40.7), "cabo delgado": (-12.5, 40.5),
    "al-shabaab": (2.0, 45.3), "boko haram": (11.85, 13.16),
    "lake chad": (13.0, 14.5), "cabo ligado": (-12.5, 40.5),
    # Latin America
    "cartel": (20.0, -102.0), "colombia": (4.6, -74.1),
    "venezuela": (10.5, -66.9),
}

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
