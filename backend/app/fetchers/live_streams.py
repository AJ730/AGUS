"""Live news stream fetcher -- discovers streams from iptv-org community database."""

from __future__ import annotations

import logging
import re
from typing import List

import httpx

from .base import BaseFetcher
from ..utils import COUNTRY_COORDS

logger = logging.getLogger("agus.fetchers")

# iptv-org community-maintained news stream playlist (updated daily)
_IPTV_NEWS_URL = "https://iptv-org.github.io/iptv/categories/news.m3u"

# Extract tvg-id tag value (contains country code like "AlJazeera.qa@HD")
_TVG_ID_RE = re.compile(r'tvg-id="([^"]*)"')
# Extract channel name (text after last comma in EXTINF line)
_NAME_RE = re.compile(r',\s*(.+)$')


def _country_from_tvg_id(tvg_id: str) -> str:
    """Extract 2-letter country code from tvg-id like 'AlJazeera.qa@HD'."""
    if not tvg_id:
        return ""
    # Format: ChannelName.CC@quality or ChannelName.CC
    parts = tvg_id.split(".")
    if len(parts) >= 2:
        cc_part = parts[-1]  # last part after dot
        cc = cc_part.split("@")[0]  # remove @quality suffix
        if len(cc) == 2 and cc.isalpha():
            return cc.lower()
    return ""


def _geocode_country(code: str):
    """Resolve ISO 2-letter country code to (lat, lon)."""
    if not code:
        return None
    coords = COUNTRY_COORDS.get(code.lower())
    if coords:
        return coords
    coords = COUNTRY_COORDS.get(code.upper())
    if coords:
        return coords
    return None


class LiveStreamFetcher(BaseFetcher):
    """Discovers live news streams from the iptv-org community database."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(client, self._from_iptv_org, self._from_youtube_rss)

    async def _from_iptv_org(self, client: httpx.AsyncClient) -> List[dict]:
        """Parse iptv-org M3U news playlist for live streams."""
        resp = await client.get(_IPTV_NEWS_URL, timeout=30.0)
        resp.raise_for_status()
        text = resp.text

        results: List[dict] = []
        seen_countries: dict = {}  # country -> count, limit per country
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF"):
                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url and not url.startswith("#"):
                        # Extract tvg-id for country code
                        tvg_match = _TVG_ID_RE.search(line)
                        tvg_id = tvg_match.group(1) if tvg_match else ""
                        country_code = _country_from_tvg_id(tvg_id)

                        # Extract channel name (after last comma)
                        name_match = _NAME_RE.search(line)
                        name = name_match.group(1).strip() if name_match else ""

                        # Skip geo-blocked or non-24/7 channels
                        if "[Geo-blocked]" in name:
                            i += 2
                            continue

                        if not country_code:
                            i += 2
                            continue

                        coords = _geocode_country(country_code)
                        if not coords:
                            i += 2
                            continue

                        # Limit to 2 streams per country to avoid clustering
                        cnt = seen_countries.get(country_code, 0)
                        if cnt >= 2:
                            i += 2
                            continue
                        seen_countries[country_code] = cnt + 1

                        lat, lon = coords
                        # Slight offset for multiple streams in same country
                        if cnt > 0:
                            lat += cnt * 0.8
                            lon += cnt * 0.6

                        results.append({
                            "name": name,
                            "stream_url": url,
                            "latitude": lat,
                            "longitude": lon,
                            "country": country_code.upper(),
                            "type": "Live News",
                            "source": "iptv-org",
                        })
                    i += 2
                    continue
            i += 1

        logger.info("iptv-org news streams: %d channels from %d countries",
                     len(results), len(seen_countries))
        return results

    async def _from_youtube_rss(self, client: httpx.AsyncClient) -> List[dict]:
        """Fallback: discover live streams from major news YouTube channels."""
        _CHANNELS = [
            ("UCNye-wNBqNL5ZzHSJj3l8Bg", "Al Jazeera English", "qa"),
            ("UCQfwfsi5VrQ8yKZ-UWmAEFg", "France 24 English", "fr"),
            ("UCknLrEdhRCp1aegoMqRaCZg", "DW News", "de"),
            ("UCu4ztI_GKEdBJuoIBBVzjaQ", "Sky News", "gb"),
            ("UCw3SFEAkLAOoTKhqdMBIKbA", "WION", "in"),
            ("UC-KCiMQ_bNmbkxMdBMH3LQA", "TRT World", "tr"),
            ("UCo8bcnLyZH8tBIH9V1mLgqQ", "TeleSUR English", "ve"),
        ]
        results: List[dict] = []
        for channel_id, name, country_code in _CHANNELS:
            coords = _geocode_country(country_code)
            if not coords:
                continue
            lat, lon = coords
            results.append({
                "name": name,
                "stream_url": f"https://www.youtube.com/channel/{channel_id}/live",
                "latitude": lat,
                "longitude": lon,
                "country": country_code.upper(),
                "language": "English",
                "type": "YouTube Live",
                "source": "youtube",
            })
        return results
