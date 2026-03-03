"""GDACS weather and natural disaster alert fetcher."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_EVENT_TYPE_MAP = {
    "EQ": "earthquake", "TC": "tropical_cyclone", "FL": "flood",
    "VO": "volcano", "DR": "drought", "WF": "wildfire", "TS": "tsunami",
}


class WeatherAlertFetcher(BaseFetcher):
    """Fetches natural disaster alerts from GDACS RSS feed."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        try:
            resp = await client.get(
                "https://www.gdacs.org/xml/rss.xml",
                timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            channel = root.find("channel")
            if channel is None:
                return []
            results: List[dict] = []
            for item in channel.findall("item"):
                lat, lon = self._parse_georss(item)
                event_type = item.findtext("{http://www.gdacs.org}eventtype") or "unknown"
                severity = item.findtext("{http://www.gdacs.org}severity")
                alert_level = item.findtext("{http://www.gdacs.org}alertlevel")
                results.append({
                    "title": (item.findtext("title") or "").strip(),
                    "description": ((item.findtext("description") or "").strip())[:500],
                    "latitude": lat, "longitude": lon,
                    "severity": alert_level or severity or "unknown",
                    "type": _EVENT_TYPE_MAP.get(event_type, event_type),
                    "country": item.findtext("{http://www.gdacs.org}country") or "",
                    "date": (item.findtext("pubDate") or "").strip(),
                    "source_url": (item.findtext("link") or "").strip(),
                })
            return results
        except Exception as exc:
            logger.warning("GDACS RSS fetch failed: %s", exc)
        return []

    @staticmethod
    def _parse_georss(item: ET.Element) -> tuple:
        point = item.findtext("{http://www.georss.org/georss}point")
        if point:
            parts = point.strip().split()
            if len(parts) == 2:
                try:
                    return float(parts[0]), float(parts[1])
                except (ValueError, TypeError):
                    pass
        return 0.0, 0.0
