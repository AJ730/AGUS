"""WarSpotting API fetcher for geocoded military equipment losses.

Primary: WarSpotting API (ukr.warspotting.net) — photo-verified equipment
losses with GPS coordinates.
Fallback: GDELT DOC API for equipment loss/destruction news articles.
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher
from ..utils import COUNTRY_COORDS

logger = logging.getLogger("agus.fetchers")

_WARSPOTTING_URL = "https://ukr.warspotting.net/api/v1"
_WARSPOTTING_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)


class EquipmentLossFetcher(BaseFetcher):
    """Fetches verified military equipment loss data from WarSpotting + GDELT."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch equipment losses from WarSpotting, falling back to GDELT."""
        return await self._collect(
            client,
            self._fetch_warspotting,
            self._fetch_gdelt_losses,
        )

    async def _fetch_warspotting(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch from WarSpotting API (photo-verified equipment losses)."""
        results: List[dict] = []
        try:
            # Try the documented API endpoint (short timeout — often unreachable from Docker)
            resp = await client.get(
                f"{_WARSPOTTING_URL}/losses",
                timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                logger.debug("WarSpotting returned %d", resp.status_code)
                return []

            data = resp.json()
            items = data if isinstance(data, list) else data.get("results", data.get("data", []))

            for item in items[:500]:
                lat = item.get("latitude") or item.get("lat")
                lon = item.get("longitude") or item.get("lon") or item.get("lng")
                if lat is None or lon is None:
                    continue

                try:
                    lat, lon = float(lat), float(lon)
                except (ValueError, TypeError):
                    continue

                status = item.get("status", "destroyed")
                equipment_type = item.get("type", item.get("equipment_type", "Unknown"))

                results.append({
                    "name": item.get("name", equipment_type),
                    "latitude": lat,
                    "longitude": lon,
                    "equipment_type": equipment_type,
                    "status": status,
                    "country": item.get("country", ""),
                    "operator": item.get("operator", item.get("unit", "")),
                    "date": item.get("date", ""),
                    "source": "WarSpotting",
                    "verified": True,
                    "photo_url": item.get("photo_url", item.get("image", "")),
                    "url": item.get("url", ""),
                    "category": item.get("category", ""),
                })

            logger.info("WarSpotting: %d equipment losses", len(results))
        except httpx.HTTPError as exc:
            logger.warning("WarSpotting fetch failed: %s", exc)
        return results

    async def _fetch_gdelt_losses(self, client: httpx.AsyncClient) -> List[dict]:
        """Fallback: mine GDELT for equipment destruction/capture reports."""
        results: List[dict] = []

        queries = [
            "military equipment destroyed ukraine russia",
            "tank destroyed drone shot down",
            "armored vehicle captured military wreckage",
        ]

        for query in queries:
            try:
                features = await self._gdelt(client, query, timespan="7D", maxrows=100)
                for feat in features:
                    props = feat.get("properties", {}) if isinstance(feat, dict) else {}
                    geom = feat.get("geometry", {})
                    coords = geom.get("coordinates", [None, None])

                    if coords[0] is None or coords[1] is None:
                        continue

                    title = props.get("name", props.get("title", "Equipment Loss"))
                    title_lower = title.lower()

                    # Infer equipment type from title
                    if any(w in title_lower for w in ["tank", "armor", "armored", "bmp", "btr"]):
                        eq_type = "Armored Vehicle"
                    elif any(w in title_lower for w in ["drone", "uav", "shahed", "bayraktar"]):
                        eq_type = "UAV/Drone"
                    elif any(w in title_lower for w in ["helicopter", "heli", "chopper"]):
                        eq_type = "Helicopter"
                    elif any(w in title_lower for w in ["aircraft", "jet", "fighter", "plane"]):
                        eq_type = "Aircraft"
                    elif any(w in title_lower for w in ["ship", "vessel", "warship", "frigate"]):
                        eq_type = "Naval Vessel"
                    elif any(w in title_lower for w in ["artillery", "howitzer", "mlrs", "himars"]):
                        eq_type = "Artillery"
                    elif any(w in title_lower for w in ["radar", "sam", "air defense", "s-300", "s-400"]):
                        eq_type = "Air Defense"
                    else:
                        eq_type = "Military Equipment"

                    # Infer status
                    if any(w in title_lower for w in ["destroyed", "wreck", "burning"]):
                        status = "destroyed"
                    elif any(w in title_lower for w in ["captured", "seized", "abandoned"]):
                        status = "captured"
                    elif any(w in title_lower for w in ["damaged", "hit"]):
                        status = "damaged"
                    else:
                        status = "reported"

                    results.append({
                        "name": title[:200],
                        "latitude": coords[1],
                        "longitude": coords[0],
                        "equipment_type": eq_type,
                        "status": status,
                        "country": props.get("country", ""),
                        "operator": "",
                        "date": props.get("date", ""),
                        "source": props.get("source", "GDELT"),
                        "verified": False,
                        "photo_url": "",
                        "url": props.get("url", ""),
                        "category": eq_type,
                    })
            except Exception as exc:
                logger.debug("GDELT equipment loss query failed: %s", exc)

        logger.info("GDELT equipment losses: %d events", len(results))
        return results
