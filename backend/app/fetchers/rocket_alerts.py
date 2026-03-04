"""Global rocket/missile alert fetcher — live alerts from multiple worldwide sources."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import httpx

from .base import BaseFetcher
from ..utils import COUNTRY_COORDS

logger = logging.getLogger("agus.fetchers")

# OREF-specific headers (Israel only)
_OREF_HEADERS = {
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
}

# High-precision city-level geocoding for conflict zones worldwide
_CITY_LOCATIONS: Dict[str, Tuple[float, float]] = {
    # Israel
    "tel aviv": (32.0853, 34.7818), "jerusalem": (31.7683, 35.2137),
    "haifa": (32.7940, 34.9896), "beer sheva": (31.2518, 34.7913),
    "be'er sheva": (31.2518, 34.7913), "ashkelon": (31.6688, 34.5743),
    "ashdod": (31.8044, 34.6553), "sderot": (31.5249, 34.5960),
    "netanya": (32.3215, 34.8532), "eilat": (29.5577, 34.9519),
    "nahariya": (33.0074, 35.0950), "kiryat shmona": (33.2079, 35.5710),
    # Gaza / Palestine
    "gaza": (31.5, 34.47), "rafah": (31.3, 34.25), "khan younis": (31.34, 34.30),
    "jabalia": (31.53, 34.48), "deir al-balah": (31.42, 34.35),
    "nuseirat": (31.45, 34.40), "beit hanoun": (31.54, 34.53),
    # Lebanon
    "beirut": (33.89, 35.50), "tyre": (33.27, 35.20), "sidon": (33.56, 35.37),
    "nabatieh": (33.38, 35.48), "baalbek": (34.01, 36.21),
    # Syria
    "damascus": (33.51, 36.29), "aleppo": (36.20, 37.16), "homs": (34.73, 36.71),
    "latakia": (35.52, 35.78), "idlib": (35.93, 36.63),
    # Ukraine
    "kyiv": (50.45, 30.52), "kharkiv": (49.99, 36.23), "odesa": (46.48, 30.73),
    "dnipro": (48.46, 35.05), "zaporizhzhia": (47.85, 35.12),
    "lviv": (49.84, 24.03), "kherson": (46.64, 32.62),
    "donetsk": (48.00, 37.80), "mariupol": (47.10, 37.55),
    # Yemen
    "sanaa": (15.35, 44.21), "aden": (12.79, 45.04), "hodeidah": (14.80, 42.95),
    "marib": (15.46, 45.32),
    # Iraq
    "baghdad": (33.31, 44.37), "erbil": (36.19, 44.01), "mosul": (36.34, 43.14),
    "basra": (30.51, 47.78),
    # Iran
    "tehran": (35.69, 51.39), "isfahan": (32.65, 51.68), "tabriz": (38.08, 46.29),
    # Korea
    "seoul": (37.57, 126.98), "pyongyang": (39.04, 125.76),
    # Pakistan/India
    "islamabad": (33.69, 73.04), "karachi": (24.86, 67.01),
    "new delhi": (28.61, 77.21), "mumbai": (19.08, 72.88),
    # Other hotspots
    "taipei": (25.03, 121.57), "riyadh": (24.71, 46.67), "jeddah": (21.54, 39.17),
    "mogadishu": (2.05, 45.32), "khartoum": (15.59, 32.53),
}

# Region-level fallback coordinates
_REGION_COORDS: Dict[str, Tuple[float, float]] = {
    "gaza envelope": (31.35, 34.45), "western negev": (31.30, 34.40),
    "golan heights": (33.00, 35.75), "upper galilee": (33.05, 35.50),
    "central israel": (32.00, 34.80), "southern israel": (31.25, 34.50),
    "northern israel": (33.00, 35.50), "west bank": (31.95, 35.25),
    "red sea": (20.0, 38.0), "gulf of aden": (12.5, 45.0),
    "strait of hormuz": (26.6, 56.3), "south china sea": (14.0, 115.0),
    "donbas": (48.0, 38.0), "crimea": (44.95, 34.1),
    "korean peninsula": (37.5, 127.0), "taiwan strait": (24.5, 119.5),
}

# Keywords that indicate a rocket/missile alert event
_ALERT_KEYWORDS = [
    "rocket", "missile", "iron dome", "air raid", "siren", "alert",
    "interception", "barrage", "projectile", "mortar", "shelling",
    "drone attack", "drone strike", "uav attack", "ballistic",
    "cruise missile", "icbm", "air defense", "air defence",
    "bomb", "airstrike", "air strike", "artillery", "thaad",
    "patriot", "s-300", "s-400", "himars", "atacms",
]

# Global news RSS feeds covering conflicts/alerts
_GLOBAL_FEEDS = [
    "https://www.timesofisrael.com/feed/",
    "https://www.i24news.tv/en/rss",
    "https://www.jpost.com/rss/rssfeedsfrontpage.aspx",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
]


def _geocode_text(text: str) -> Tuple[str, Tuple[float, float]] | Tuple[None, None]:
    """Geocode text by matching city names, regions, then country names."""
    text_lower = text.lower()
    # Try city-level first (highest precision)
    for city, coords in _CITY_LOCATIONS.items():
        if city in text_lower:
            return city.title(), coords
    # Try region-level
    for region, coords in _REGION_COORDS.items():
        if region in text_lower:
            return region.title(), coords
    # Try country-level from COUNTRY_COORDS (full names, sorted longest first)
    country_names = sorted(
        (k for k in COUNTRY_COORDS if len(k) > 2),
        key=len, reverse=True,
    )
    for name in country_names:
        if name.lower() in text_lower:
            lat, lon = COUNTRY_COORDS[name]
            return name, (lat, lon)
    return None, None


class RocketAlertFetcher(BaseFetcher):
    """Fetches global rocket/missile alerts from live APIs and news feeds."""

    async def _from_tzevaadom(self, client: httpx.AsyncClient) -> List[dict]:
        """Try Tzeva Adom community API (Israel live alerts)."""
        results: List[dict] = []
        try:
            resp = await client.get(
                "https://api.tzevaadom.co.il/notifications",
                headers={"Accept": "application/json"},
                timeout=15.0,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            alerts = data if isinstance(data, list) else data.get("alerts", data.get("notifications", []))
            now_iso = datetime.now(timezone.utc).isoformat()
            for alert in alerts[:100]:
                locations = alert.get("cities", alert.get("data", alert.get("locations", "")))
                if isinstance(locations, str):
                    locations = [locations] if locations else []
                elif not isinstance(locations, list):
                    continue
                threat = alert.get("threat", alert.get("cat", "rockets"))
                alert_time = alert.get("time", alert.get("alertDate", now_iso))

                for loc_name in locations:
                    if not isinstance(loc_name, str) or not loc_name.strip():
                        continue
                    name, coords = _geocode_text(loc_name)
                    if not coords:
                        continue
                    results.append({
                        "title": f"Alert: {loc_name}",
                        "latitude": coords[0],
                        "longitude": coords[1],
                        "location": loc_name,
                        "alert_type": str(threat),
                        "severity": "critical",
                        "date": str(alert_time),
                        "source": "Tzeva Adom",
                        "type": "rocket_alert",
                    })
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.debug("Tzeva Adom API: %s", exc)
        return results

    async def _from_oref(self, client: httpx.AsyncClient) -> List[dict]:
        """Try official OREF endpoints (Israel)."""
        results: List[dict] = []
        oref_urls = [
            "https://www.oref.org.il/WarningMessages/alert/alerts.json",
            "https://www.oref.org.il/warningMessages/alert/History/AlertsHistory.json",
        ]
        for url in oref_urls:
            try:
                resp = await client.get(
                    url, headers=_OREF_HEADERS,
                    timeout=httpx.Timeout(connect=10.0, read=15.0, write=5.0, pool=10.0),
                )
                if resp.status_code != 200:
                    continue
                text = resp.text.strip()
                if not text or text in ("[]", "null"):
                    continue
                if text.startswith("\ufeff"):
                    text = text[1:]

                import json
                alerts = json.loads(text)
                if not isinstance(alerts, list):
                    alerts = [alerts]

                for alert in alerts:
                    locations: list = []
                    if isinstance(alert.get("data"), list):
                        locations = alert["data"]
                    elif isinstance(alert.get("data"), str):
                        locations = [alert["data"]]

                    alert_title = alert.get("title", "Alert")
                    alert_cat = str(alert.get("cat", "1"))
                    alert_date = alert.get("alertDate", alert.get("date", ""))

                    alert_type = {
                        "1": "rocket_alert", "2": "uav_intrusion",
                        "3": "earthquake", "6": "hostile_aircraft",
                    }.get(alert_cat, "rocket_alert")

                    for loc_name in locations:
                        if not isinstance(loc_name, str):
                            continue
                        name, coords = _geocode_text(loc_name)
                        if not coords:
                            continue
                        results.append({
                            "title": f"{alert_title}: {loc_name}",
                            "latitude": coords[0],
                            "longitude": coords[1],
                            "location": loc_name,
                            "alert_type": alert_type,
                            "severity": "critical",
                            "date": alert_date,
                            "source": "OREF",
                            "type": "rocket_alert",
                        })
                if results:
                    break
            except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
                logger.debug("OREF %s: %s", url.split("/")[-1], exc)
        return results

    async def _from_news_rss(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch global rocket/missile alert news from international RSS feeds."""
        results: List[dict] = []
        seen_titles: set = set()
        for feed_url in _GLOBAL_FEEDS:
            try:
                resp = await client.get(feed_url, timeout=15.0)
                if resp.status_code != 200:
                    continue
                root = ET.fromstring(resp.content)
                for item in root.iter("item"):
                    title = (item.findtext("title") or "").strip()
                    title_lower = title.lower()
                    if not any(kw in title_lower for kw in _ALERT_KEYWORDS):
                        continue
                    # Deduplicate by title
                    title_key = title_lower[:60]
                    if title_key in seen_titles:
                        continue
                    seen_titles.add(title_key)
                    # Geocode globally
                    loc_name, coords = _geocode_text(title)
                    if not coords:
                        continue
                    pub_date = item.findtext("pubDate") or ""
                    link = item.findtext("link") or ""
                    results.append({
                        "title": title[:200],
                        "latitude": coords[0],
                        "longitude": coords[1],
                        "location": loc_name,
                        "alert_type": "rocket_alert",
                        "severity": "high",
                        "date": pub_date,
                        "url": link,
                        "source": "News RSS",
                        "type": "rocket_alert",
                    })
            except (httpx.HTTPError, httpx.TimeoutException, ET.ParseError) as exc:
                logger.debug("RSS alert feed %s: %s", feed_url.split("/")[2], exc)
        logger.info("News RSS rocket/missile alerts: %d from %d feeds",
                     len(results), len(_GLOBAL_FEEDS))
        return results

    async def _from_gdelt_alerts(self, client: httpx.AsyncClient) -> List[dict]:
        """Fallback: global rocket/missile alert news from GDELT DOC API."""
        results: List[dict] = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as doc_client:
                resp = await doc_client.get(
                    "http://api.gdeltproject.org/api/v2/doc/doc",
                    params={
                        "query": (
                            '("missile attack" OR "rocket attack" OR "air strike" OR '
                            '"drone strike" OR "ballistic missile" OR "air raid" OR '
                            '"iron dome" OR "air defense" OR "missile launch" OR '
                            '"shelling" OR "bombardment") sourcelang:english'
                        ),
                        "mode": "ArtList",
                        "maxrecords": "75",
                        "format": "json",
                        "TIMESPAN": "14D",
                    },
                )
            if resp.status_code != 200:
                return []
            articles = resp.json().get("articles") or []
            for art in articles:
                title = (art.get("title") or "")[:200]
                loc_name, coords = _geocode_text(title)
                if not coords:
                    # Try sourcecountry field
                    sc = (art.get("sourcecountry") or "").strip()
                    c = COUNTRY_COORDS.get(sc) or COUNTRY_COORDS.get(sc.lower())
                    if c:
                        coords = c
                        loc_name = sc
                    else:
                        continue
                results.append({
                    "title": title,
                    "latitude": coords[0],
                    "longitude": coords[1],
                    "location": loc_name,
                    "alert_type": "rocket_alert",
                    "severity": "high",
                    "date": art.get("seendate", ""),
                    "url": art.get("url", ""),
                    "source": "GDELT",
                    "type": "rocket_alert",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.debug("GDELT rocket alerts: %s", exc)
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch from all sources: live APIs, global news RSS, then GDELT."""
        results = await self._collect(
            client,
            self._from_tzevaadom,
            self._from_oref,
            self._from_news_rss,
            self._from_gdelt_alerts,
        )
        logger.info("Rocket alerts: %d total from all sources", len(results))
        return results
