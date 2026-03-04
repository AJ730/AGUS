"""GeoConfirmed + Bellingcat verified conflict events fetcher."""

from __future__ import annotations

import asyncio
import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")


class GeoConfirmedFetcher(BaseFetcher):
    """Fetches verified geolocated conflict events from GeoConfirmed + Bellingcat."""

    async def _from_geoconfirmed(self, client: httpx.AsyncClient) -> List[dict]:
        """Try osint-geo-extractor library for GeoConfirmed data."""
        results: List[dict] = []
        try:
            from geo_extractor import get_geoconfirmed_data
            events = await asyncio.wait_for(
                asyncio.to_thread(get_geoconfirmed_data), timeout=60.0,
            )
            for ev in events:
                lat = getattr(ev, 'latitude', None)
                lon = getattr(ev, 'longitude', None)
                if lat is None or lon is None:
                    continue
                title = getattr(ev, 'title', '') or getattr(ev, 'place_desc', 'Verified Event')
                date = getattr(ev, 'date', '')
                desc = getattr(ev, 'description', '')
                links = getattr(ev, 'links', []) or []

                results.append({
                    "title": str(title)[:200],
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "description": str(desc)[:300],
                    "date": str(date) if date else "",
                    "media_urls": links[:3],
                    "source": "GeoConfirmed",
                    "type": "geo_confirmed",
                    "verified": True,
                })
        except ImportError:
            logger.debug("osint-geo-extractor not installed, skipping GeoConfirmed")
        except Exception as exc:
            logger.warning("GeoConfirmed fetch: %s", exc)
        return results

    async def _from_bellingcat(self, client: httpx.AsyncClient) -> List[dict]:
        """Try Bellingcat Ukraine data."""
        results: List[dict] = []
        try:
            from geo_extractor import get_bellingcat_data
            events = await asyncio.wait_for(
                asyncio.to_thread(get_bellingcat_data), timeout=60.0,
            )
            for ev in events[:200]:
                lat = getattr(ev, 'latitude', None)
                lon = getattr(ev, 'longitude', None)
                if lat is None or lon is None:
                    continue
                title = getattr(ev, 'title', '') or getattr(ev, 'place_desc', 'Bellingcat Event')
                date = getattr(ev, 'date', '')
                desc = getattr(ev, 'description', '')
                links = getattr(ev, 'links', []) or []

                results.append({
                    "title": str(title)[:200],
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "description": str(desc)[:300],
                    "date": str(date) if date else "",
                    "media_urls": links[:3],
                    "source": "Bellingcat",
                    "type": "geo_confirmed",
                    "verified": True,
                })
        except ImportError:
            logger.debug("osint-geo-extractor not installed, skipping Bellingcat")
        except Exception as exc:
            logger.warning("Bellingcat fetch: %s", exc)
        return results

    async def _from_gdelt_verified(self, client: httpx.AsyncClient) -> List[dict]:
        """Fallback: GDELT conflict verification events."""
        results: List[dict] = []
        try:
            features = await self._gdelt(
                client,
                '("confirmed" OR "verified" OR "geolocated") (attack OR strike OR explosion OR bombing)',
                "14D", 100,
            )
            for feat in features:
                coords = (feat.get("geometry") or {}).get("coordinates")
                if not coords:
                    continue
                props = feat.get("properties") or {}
                results.append({
                    "title": props.get("name", "Conflict Event")[:200],
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "date": props.get("date", ""),
                    "description": "",
                    "source": "GDELT Verified",
                    "type": "geo_confirmed",
                    "verified": False,
                    "url": props.get("url", ""),
                })
        except Exception as exc:
            logger.debug("GDELT verified events: %s", exc)
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._collect(
            client,
            self._from_geoconfirmed,
            self._from_bellingcat,
            self._from_gdelt_verified,
        )
