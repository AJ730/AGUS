"""Infrastructure layer fetchers — undersea cables from GitHub dataset."""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")


class UnderseaCableFetcher(BaseFetcher):
    """Fetches submarine cable landing points from GitHub-hosted TeleGeography data."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(
            client,
            self._from_github_cables,
            self._from_telegeography,
        )

    async def _from_github_cables(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch cable data from GitHub (reliable from Docker)."""
        results: List[dict] = []

        # Landing points from GitHub-hosted dataset
        try:
            resp = await client.get(
                "https://raw.githubusercontent.com/telegeography/www.submarinecablemap.com/master/web/public/api/v3/landing-point/landing-point-geo.json",
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0),
            )
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", []) if isinstance(data, dict) else []

            for feat in features:
                coords = (feat.get("geometry") or {}).get("coordinates")
                if not coords or len(coords) < 2:
                    continue
                props = feat.get("properties") or {}
                results.append({
                    "title": props.get("name", "Landing Point"),
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "country": props.get("country", ""),
                    "cable_count": len(props.get("cables", "").split(",")) if props.get("cables") else 0,
                    "cables": props.get("cables", ""),
                    "source": "TeleGeography",
                    "type": "undersea_cable",
                })
        except Exception as exc:
            logger.warning("GitHub undersea cables: %s", exc)

        # Cable routes
        try:
            resp = await client.get(
                "https://raw.githubusercontent.com/telegeography/www.submarinecablemap.com/master/web/public/api/v3/cable/cable-geo.json",
                timeout=httpx.Timeout(connect=10.0, read=60.0, write=5.0, pool=10.0),
            )
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", []) if isinstance(data, dict) else []

            for feat in features[:200]:
                props = feat.get("properties") or {}
                geom = feat.get("geometry") or {}
                coords = geom.get("coordinates", [])
                if not coords:
                    continue

                if geom.get("type") == "MultiLineString" and coords:
                    first_seg = coords[0]
                    last_seg = coords[-1]
                    if first_seg and last_seg:
                        start = first_seg[0]
                        end = last_seg[-1]
                        if len(start) >= 2 and len(end) >= 2:
                            mid_lat = (start[1] + end[1]) / 2
                            mid_lon = (start[0] + end[0]) / 2
                            results.append({
                                "title": props.get("name", "Submarine Cable"),
                                "latitude": mid_lat,
                                "longitude": mid_lon,
                                "cable_length": props.get("length", ""),
                                "rfs": props.get("rfs", ""),
                                "owners": props.get("owners", ""),
                                "source": "TeleGeography",
                                "type": "undersea_cable_route",
                                "from_lat": start[1],
                                "from_lon": start[0],
                                "to_lat": end[1],
                                "to_lon": end[0],
                            })
        except Exception as exc:
            logger.debug("Cable routes: %s", exc)

        logger.info("Undersea cables: %d items", len(results))
        return results

    async def _from_telegeography(self, client: httpx.AsyncClient) -> List[dict]:
        """Fallback: direct submarinecablemap.com API."""
        results: List[dict] = []
        try:
            resp = await client.get(
                "https://www.submarinecablemap.com/api/v3/landing-point/landing-point-geo.json",
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0),
            )
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", []) if isinstance(data, dict) else []

            for feat in features:
                coords = (feat.get("geometry") or {}).get("coordinates")
                if not coords or len(coords) < 2:
                    continue
                props = feat.get("properties") or {}
                results.append({
                    "title": props.get("name", "Landing Point"),
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "country": props.get("country", ""),
                    "cable_count": len(props.get("cables", "").split(",")) if props.get("cables") else 0,
                    "cables": props.get("cables", ""),
                    "source": "TeleGeography",
                    "type": "undersea_cable",
                })
        except Exception as exc:
            logger.warning("TeleGeography API: %s", exc)
        return results
