"""Mastodon OSINT fetcher — trending posts from security/OSINT instances.

Fetches trending posts and links from infosec/OSINT Mastodon instances.
Free, no authentication required (public API).
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

import httpx

from ..utils import COUNTRY_COORDS
from .base import BaseFetcher
from .conflict_zones import CONFLICT_ZONES as _CONFLICT_ZONES

logger = logging.getLogger("agus.fetchers")

_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)

# Public Mastodon instances with OSINT/security communities
_INSTANCES = [
    "mastodon.social",
    "infosec.exchange",
]

# Conflict/security keywords for filtering
_KEYWORDS = re.compile(
    r"(?i)(attack|strike|drone|missile|bomb|explosion|shoot|conflict|war|"
    r"military|terrorism|cyber|hack|breach|malware|exploit|vulnerability|"
    r"earthquake|flood|hurricane|fire|volcano|nuclear|radiation|"
    r"russia|ukraine|gaza|israel|iran|china|taiwan|korea|syria|yemen|"
    r"nato|army|navy|airforce|intelligence|espionage|osint|geoint|sigint|"
    r"sanction|weapon|artillery|tank|helicopter|fighter|submarine)",
)



class MastodonOSINTFetcher(BaseFetcher):
    """Fetches trending OSINT posts from Mastodon security instances."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch trending posts from OSINT Mastodon instances."""
        return await self._collect(
            client,
            *(self._make_instance_fn(inst) for inst in _INSTANCES),
        )

    def _make_instance_fn(self, instance: str):
        """Create a fetch function for a specific Mastodon instance."""
        async def _fn(client: httpx.AsyncClient) -> List[dict]:
            return await self._fetch_instance(client, instance)
        _fn.__name__ = f"mastodon_{instance}"
        return _fn

    async def _fetch_instance(
        self, client: httpx.AsyncClient, instance: str
    ) -> List[dict]:
        """Fetch trending statuses from a Mastodon instance."""
        results: List[dict] = []
        try:
            resp = await client.get(
                f"https://{instance}/api/v1/trends/statuses",
                timeout=_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            statuses = resp.json()

            for status in statuses[:40]:
                content = status.get("content", "")
                # Strip HTML tags for text analysis
                text = re.sub(r"<[^>]+>", " ", content).strip()

                if not _KEYWORDS.search(text):
                    continue

                # Geocode from text
                lat, lon = self._geocode_text(text)
                if lat is None:
                    continue

                account = status.get("account", {})
                author = account.get("display_name") or account.get("username", "")

                results.append({
                    "name": text[:120],
                    "latitude": lat,
                    "longitude": lon,
                    "author": author,
                    "instance": instance,
                    "url": status.get("url", ""),
                    "date": status.get("created_at", ""),
                    "reblogs": status.get("reblogs_count", 0),
                    "favourites": status.get("favourites_count", 0),
                    "source": f"Mastodon ({instance})",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Mastodon [%s] fetch failed: %s", instance, exc)

        # Also try trending links
        try:
            resp = await client.get(
                f"https://{instance}/api/v1/trends/links",
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            links = resp.json()
            for link in links[:20]:
                title = link.get("title", "")
                desc = link.get("description", "")
                combined = f"{title} {desc}"
                if not _KEYWORDS.search(combined):
                    continue
                lat, lon = self._geocode_text(combined)
                if lat is None:
                    continue
                results.append({
                    "name": title[:120],
                    "latitude": lat,
                    "longitude": lon,
                    "author": link.get("provider_name", ""),
                    "instance": instance,
                    "url": link.get("url", ""),
                    "date": link.get("published_at", ""),
                    "source": f"Mastodon ({instance})",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Mastodon links [%s] failed: %s", instance, exc)

        logger.info("Mastodon [%s]: %d OSINT posts", instance, len(results))
        return results

    @staticmethod
    def _geocode_text(text: str) -> Tuple[Optional[float], Optional[float]]:
        """Extract location from text using conflict zone keywords + country names."""
        text_lower = text.lower()

        # Check conflict zones first (most specific)
        for zone, (lat, lon) in _CONFLICT_ZONES.items():
            if zone in text_lower:
                return lat, lon

        # Check country names
        for name, (lat, lon) in COUNTRY_COORDS.items():
            if name.lower() in text_lower:
                return lat, lon

        return None, None
