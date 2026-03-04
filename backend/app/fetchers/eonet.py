"""NASA EONET (Earth Observatory Natural Event Tracker) fetcher.

Fetches active natural events from NASA's EONET API v3.
Free, no authentication required.
URL: https://eonet.gsfc.nasa.gov/api/v3/events
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
_EONET_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)

# Map EONET category IDs to human-readable labels
_CATEGORY_MAP = {
    "wildfires": "Wildfire",
    "volcanoes": "Volcano",
    "severeStorms": "Severe Storm",
    "seaLakeIce": "Sea/Lake Ice",
    "earthquakes": "Earthquake",
    "floods": "Flood",
    "landslides": "Landslide",
    "drought": "Drought",
    "dustHaze": "Dust/Haze",
    "tempExtremes": "Temperature Extreme",
    "waterColor": "Water Discoloration",
    "manmade": "Manmade Event",
    "snow": "Snow",
}


class EONETFetcher(BaseFetcher):
    """Fetches active natural events from NASA EONET v3 API."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch natural events from EONET."""
        return await self._try_sources(
            client,
            self._fetch_eonet,
            self._fetch_gdelt_natural,
        )

    async def _fetch_eonet(self, client: httpx.AsyncClient) -> List[dict]:
        """Primary: NASA EONET v3 API."""
        results: List[dict] = []
        try:
            resp = await client.get(
                _EONET_URL,
                params={"status": "open", "limit": 200},
                timeout=_EONET_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            events = data.get("events", [])

            for event in events:
                # Get the most recent geometry (EONET events can have multiple geometries over time)
                geometries = event.get("geometry", event.get("geometries", []))
                if not geometries:
                    continue

                # Use the most recent geometry
                geom = geometries[-1] if isinstance(geometries, list) else geometries
                coords = geom.get("coordinates", [])

                if not coords or len(coords) < 2:
                    continue

                # EONET uses [lon, lat] order
                lon, lat = coords[0], coords[1]
                if not (isinstance(lon, (int, float)) and isinstance(lat, (int, float))):
                    continue

                # Extract category
                categories = event.get("categories", [])
                cat_id = categories[0].get("id", "unknown") if categories else "unknown"
                cat_label = _CATEGORY_MAP.get(cat_id, cat_id.replace("_", " ").title())

                # Extract date
                date = geom.get("date", "")

                # Extract sources
                sources = event.get("sources", [])
                source_url = sources[0].get("url", "") if sources else ""

                # Magnitude
                mag_value = geom.get("magnitudeValue")
                mag_unit = geom.get("magnitudeUnit", "")

                results.append({
                    "name": event.get("title", "Natural Event")[:200],
                    "latitude": lat,
                    "longitude": lon,
                    "category": cat_label,
                    "category_id": cat_id,
                    "date": str(date),
                    "source": "NASA EONET",
                    "magnitude": f"{mag_value} {mag_unit}".strip() if mag_value else "",
                    "url": source_url,
                    "event_id": event.get("id", ""),
                    "closed": event.get("closed") or "",
                })

            logger.info("EONET: %d natural events", len(results))
        except httpx.HTTPError as exc:
            logger.warning("EONET fetch failed: %s", exc)
        return results

    async def _fetch_gdelt_natural(self, client: httpx.AsyncClient) -> List[dict]:
        """Fallback: GDELT news for natural disaster reports."""
        results: List[dict] = []
        try:
            features = await self._gdelt(
                client,
                "volcano eruption OR wildfire OR hurricane OR earthquake damage OR flood disaster",
                timespan="7D",
                maxrows=100,
            )
            for feat in features:
                props = feat.get("properties", {}) if isinstance(feat, dict) else {}
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [None, None])

                if coords[0] is None or coords[1] is None:
                    continue

                title = props.get("name", "Natural Event")
                title_lower = title.lower()

                # Infer category from title
                if any(w in title_lower for w in ["fire", "wildfire", "blaze", "burn"]):
                    category = "Wildfire"
                elif any(w in title_lower for w in ["volcano", "eruption", "lava"]):
                    category = "Volcano"
                elif any(w in title_lower for w in ["hurricane", "typhoon", "cyclone", "storm"]):
                    category = "Severe Storm"
                elif any(w in title_lower for w in ["earthquake", "quake", "seismic"]):
                    category = "Earthquake"
                elif any(w in title_lower for w in ["flood", "flooding"]):
                    category = "Flood"
                else:
                    category = "Natural Event"

                results.append({
                    "name": title[:200],
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "category": category,
                    "category_id": category.lower().replace(" ", "_"),
                    "date": props.get("date", ""),
                    "source": props.get("source", "GDELT"),
                    "magnitude": "",
                    "url": props.get("url", ""),
                    "event_id": "",
                    "closed": "",
                })
        except Exception as exc:
            logger.debug("GDELT natural events failed: %s", exc)
        return results
