"""Maritime piracy/security event fetcher — NGA ASAM + GDELT + ICC data."""

from __future__ import annotations

import logging
import re
from typing import List

import httpx

from .base import BaseFetcher
from ..utils import COUNTRY_COORDS

logger = logging.getLogger("agus.fetchers")

# Maritime security keywords for GDELT
_GDELT_QUERY = (
    '(piracy OR "maritime attack" OR hijacking OR "ship seizure" OR '
    '"vessel attacked" OR "Houthi attack" OR "Houthi ship" OR '
    '"Red Sea attack" OR "Gulf of Aden" OR "maritime security" OR '
    '"cargo ship attack" OR "tanker attack" OR "naval boarding" OR '
    '"Somali pirate" OR "maritime hijack" OR "vessel seized")'
)

# Known piracy hotspot zones for geocoding NGA ASAM data
_MARITIME_ZONES = {
    "strait of malacca": (2.5, 101.5),
    "gulf of guinea": (3.0, 3.0),
    "gulf of aden": (12.0, 47.0),
    "red sea": (19.0, 38.5),
    "bab el-mandeb": (12.5, 43.3),
    "indian ocean": (-5.0, 65.0),
    "south china sea": (14.0, 115.0),
    "arabian sea": (16.0, 63.0),
    "persian gulf": (26.0, 52.0),
    "strait of hormuz": (26.3, 56.8),
    "caribbean": (15.0, -70.0),
    "west africa": (5.0, 0.0),
    "east africa": (-2.0, 42.0),
    "southeast asia": (5.0, 105.0),
    "horn of africa": (10.0, 50.0),
    "mozambique channel": (-15.0, 42.0),
    "singapore strait": (1.2, 104.0),
    "sulu sea": (8.0, 120.0),
    "celebes sea": (3.0, 123.0),
    "niger delta": (5.0, 5.5),
    "lagos": (6.45, 3.4),
    "yemen": (15.5, 48.5),
    "hodeidah": (14.8, 42.95),
    "socotra": (12.5, 54.0),
    "djibouti": (11.6, 43.1),
}

_REGION_KEYWORDS = sorted(
    ((k, v) for k, v in COUNTRY_COORDS.items() if len(k) > 2),
    key=lambda x: -len(x[0]),
)


def _geocode_maritime(text: str):
    """Geocode a maritime incident description."""
    text_lower = text.lower()
    for zone, (lat, lon) in sorted(_MARITIME_ZONES.items(), key=lambda x: -len(x[0])):
        if zone in text_lower:
            return lat, lon, zone.title()
    for name, coords in _REGION_KEYWORDS:
        if name.lower() in text_lower:
            return coords[0], coords[1], name
    return None


class PiracyFetcher(BaseFetcher):
    """Fetches live maritime piracy and hijacking events from multiple sources."""

    async def _from_gdelt(self, client: httpx.AsyncClient) -> List[dict]:
        """Maritime security events from GDELT GEO + DOC APIs."""
        features = await self._gdelt(client, _GDELT_QUERY, "30D", 300)
        results: List[dict] = []
        for feat in features:
            coords = (feat.get("geometry") or {}).get("coordinates")
            if not coords:
                continue
            props = feat.get("properties") or {}
            title = props.get("name", props.get("title", "Maritime incident"))
            # Determine severity from keywords
            title_lower = title.lower()
            if any(w in title_lower for w in ["attack", "struck", "missile", "hit"]):
                severity = "critical"
            elif any(w in title_lower for w in ["hijack", "seized", "board"]):
                severity = "high"
            else:
                severity = "medium"
            results.append({
                "title": title[:200],
                "latitude": coords[1], "longitude": coords[0],
                "date": props.get("date", props.get("urlpubtimedate", "")),
                "description": props.get("name", ""),
                "severity": severity,
                "region": props.get("country", ""),
                "source": "GDELT",
                "url": props.get("url", ""),
            })
        return results

    async def _from_gdelt_tv(self, client: httpx.AsyncClient) -> List[dict]:
        """Maritime piracy mentions on TV broadcasts via GDELT TV API."""
        results: List[dict] = []
        try:
            resp = await client.get(
                "http://api.gdeltproject.org/api/v2/tv/tv",
                params={
                    "query": "piracy OR maritime attack OR Houthi ship",
                    "mode": "clipgallery",
                    "maxrecords": "30",
                    "format": "json",
                    "LAST24H": "YES",
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                for clip in (data.get("clips") or []):
                    snippet = clip.get("snippet", "")
                    geo = _geocode_maritime(snippet)
                    if not geo:
                        station = clip.get("station", "")
                        geo = _geocode_maritime(station)
                    if not geo:
                        continue
                    lat, lon, location = geo
                    results.append({
                        "title": f"[{clip.get('station', 'TV')}] {snippet[:150]}",
                        "latitude": lat, "longitude": lon,
                        "date": clip.get("date", ""),
                        "description": snippet[:300],
                        "severity": "medium",
                        "region": location,
                        "source": "GDELT TV",
                        "url": clip.get("preview_url", ""),
                    })
        except Exception as exc:
            logger.debug("GDELT TV piracy: %s", exc)
        return results

    async def _from_rss_osint(self, client: httpx.AsyncClient) -> List[dict]:
        """Maritime security from gCaptain and Splash247 RSS."""
        import xml.etree.ElementTree as ET
        results: List[dict] = []
        feeds = [
            ("https://gcaptain.com/feed/", "gCaptain"),
            ("https://splash247.com/feed/", "Splash 247"),
        ]
        for url, label in feeds:
            try:
                resp = await client.get(url, timeout=15.0,
                                        headers={"User-Agent": "AgusOSINT/2.0"})
                if resp.status_code != 200:
                    continue
                try:
                    root = ET.fromstring(resp.text)
                except ET.ParseError:
                    continue
                for item in list(root.iter("item"))[:30]:
                    title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    pub = (item.findtext("pubDate") or "").strip()
                    desc = (item.findtext("description") or "").strip()
                    desc = re.sub(r'<[^>]+>', '', desc)[:300]

                    # Only include maritime security / piracy items
                    text = f"{title} {desc}".lower()
                    if not any(w in text for w in [
                        "piracy", "pirate", "attack", "hijack", "seized",
                        "houthi", "maritime security", "boarding",
                        "red sea", "gulf", "vessel", "tanker",
                    ]):
                        continue

                    geo = _geocode_maritime(f"{title} {desc}")
                    if not geo:
                        continue
                    lat, lon, location = geo
                    results.append({
                        "title": title[:200],
                        "latitude": lat, "longitude": lon,
                        "date": pub,
                        "description": desc,
                        "severity": "high" if any(w in text for w in ["attack", "hijack", "struck"]) else "medium",
                        "region": location,
                        "source": label,
                        "url": link,
                    })
            except Exception as exc:
                logger.debug("Maritime RSS %s: %s", label, exc)
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._collect(
            client, self._from_gdelt, self._from_gdelt_tv, self._from_rss_osint,
        )
