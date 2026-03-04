"""Space launch fetcher — TheSpaceDevs Launch Library 2.

Fetches upcoming and recent rocket launches worldwide.
Free, no authentication required.
URL: https://ll.thespacedevs.com/2.2.0/launch/
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_LL2_URL = "https://ll.thespacedevs.com/2.2.0/launch"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)


class SpaceLaunchFetcher(BaseFetcher):
    """Fetches upcoming and recent rocket launches from Launch Library 2."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch upcoming + recent launches."""
        return await self._collect(
            client,
            self._fetch_upcoming,
            self._fetch_previous,
        )

    async def _fetch_upcoming(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch upcoming launches."""
        results: List[dict] = []
        try:
            resp = await client.get(
                f"{_LL2_URL}/upcoming/",
                params={"limit": 30, "mode": "detailed"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            for launch in data.get("results", []):
                pad = launch.get("pad") or {}
                lat = pad.get("latitude")
                lon = pad.get("longitude")
                if lat is None or lon is None:
                    continue
                try:
                    lat, lon = float(lat), float(lon)
                except (ValueError, TypeError):
                    continue

                rocket = launch.get("rocket") or {}
                config = rocket.get("configuration") or {}
                mission = launch.get("mission") or {}
                provider = launch.get("launch_service_provider") or {}
                status = launch.get("status") or {}

                results.append({
                    "name": launch.get("name", "Unknown Launch"),
                    "latitude": lat,
                    "longitude": lon,
                    "status": status.get("name", "Unknown"),
                    "status_abbrev": status.get("abbrev", ""),
                    "net": launch.get("net", ""),
                    "window_start": launch.get("window_start", ""),
                    "window_end": launch.get("window_end", ""),
                    "rocket": config.get("full_name", config.get("name", "")),
                    "provider": provider.get("name", ""),
                    "mission_name": mission.get("name", ""),
                    "mission_type": mission.get("type", ""),
                    "orbit": (mission.get("orbit") or {}).get("name", ""),
                    "pad_name": pad.get("name", ""),
                    "location": (pad.get("location") or {}).get("name", ""),
                    "image": launch.get("image", ""),
                    "webcast_live": launch.get("webcast_live", False),
                    "upcoming": True,
                    "source": "Launch Library 2",
                })
            logger.info("SpaceLaunches upcoming: %d", len(results))
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("SpaceLaunches upcoming fetch failed: %s", exc)
        return results

    async def _fetch_previous(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch recent past launches."""
        results: List[dict] = []
        try:
            resp = await client.get(
                f"{_LL2_URL}/previous/",
                params={"limit": 15, "mode": "detailed"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            for launch in data.get("results", []):
                pad = launch.get("pad") or {}
                lat = pad.get("latitude")
                lon = pad.get("longitude")
                if lat is None or lon is None:
                    continue
                try:
                    lat, lon = float(lat), float(lon)
                except (ValueError, TypeError):
                    continue

                rocket = launch.get("rocket") or {}
                config = rocket.get("configuration") or {}
                mission = launch.get("mission") or {}
                provider = launch.get("launch_service_provider") or {}
                status = launch.get("status") or {}

                results.append({
                    "name": launch.get("name", "Unknown Launch"),
                    "latitude": lat,
                    "longitude": lon,
                    "status": status.get("name", "Unknown"),
                    "status_abbrev": status.get("abbrev", ""),
                    "net": launch.get("net", ""),
                    "rocket": config.get("full_name", config.get("name", "")),
                    "provider": provider.get("name", ""),
                    "mission_name": mission.get("name", ""),
                    "mission_type": mission.get("type", ""),
                    "orbit": (mission.get("orbit") or {}).get("name", ""),
                    "pad_name": pad.get("name", ""),
                    "location": (pad.get("location") or {}).get("name", ""),
                    "upcoming": False,
                    "source": "Launch Library 2",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("SpaceLaunches previous fetch failed: %s", exc)
        return results
