"""GPS/GNSS jamming and spoofing zone detection.

Sources:
1. GDELT news for GPS jamming/spoofing reports
2. Known static jamming hotspots (well-documented zones)
3. Future: derive from ADS-B NIC values in flight data

GPS jamming correlates with military operations and is a key electronic
warfare indicator — especially around Russia, Syria, and the Baltic.
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

# Known persistent GPS jamming/spoofing hotspots (well-documented)
_KNOWN_JAMMING_ZONES = [
    {
        "name": "Eastern Mediterranean GPS Spoofing Zone",
        "latitude": 34.8, "longitude": 33.5, "radius_km": 300,
        "severity": "high", "type": "spoofing",
        "description": "Persistent GPS spoofing affecting aircraft and ships. Linked to Russian military electronic warfare.",
        "source": "OPSGROUP / Eurocontrol",
    },
    {
        "name": "Black Sea GPS Jamming Zone",
        "latitude": 43.5, "longitude": 34.0, "radius_km": 250,
        "severity": "high", "type": "jamming",
        "description": "Active GPS jamming zone around Crimea and Black Sea. Russian EW systems.",
        "source": "NATO / Eurocontrol",
    },
    {
        "name": "Baltic Sea GPS Interference",
        "latitude": 57.0, "longitude": 21.0, "radius_km": 200,
        "severity": "medium", "type": "jamming",
        "description": "Recurring GPS interference near Kaliningrad. Russian EW systems affect Baltic air traffic.",
        "source": "OPSGROUP / Nordic ATC",
    },
    {
        "name": "Northern Syria / Turkey Border EW Zone",
        "latitude": 36.5, "longitude": 38.0, "radius_km": 200,
        "severity": "high", "type": "jamming",
        "description": "Active electronic warfare zone. Multiple state actors deploying GPS denial systems.",
        "source": "OPSGROUP",
    },
    {
        "name": "Israel / Gaza Border GPS Spoofing",
        "latitude": 31.5, "longitude": 34.5, "radius_km": 100,
        "severity": "critical", "type": "spoofing",
        "description": "IDF GPS spoofing to protect against drone/missile targeting. Affects civilian aviation.",
        "source": "Eurocontrol / OPSGROUP",
    },
    {
        "name": "Iraq / Iran Border EW Zone",
        "latitude": 33.5, "longitude": 45.5, "radius_km": 200,
        "severity": "medium", "type": "jamming",
        "description": "GPS interference near Iran-Iraq border. IRGC electronic warfare activity.",
        "source": "OPSGROUP",
    },
    {
        "name": "Persian Gulf GPS Interference",
        "latitude": 26.5, "longitude": 52.0, "radius_km": 150,
        "severity": "medium", "type": "spoofing",
        "description": "Intermittent GPS spoofing in Strait of Hormuz area. Affects shipping.",
        "source": "US Maritime Advisory",
    },
    {
        "name": "Ukraine Conflict EW Zone",
        "latitude": 48.5, "longitude": 37.5, "radius_km": 300,
        "severity": "critical", "type": "jamming",
        "description": "Intense GPS/GNSS jamming across the Ukraine front line. Both sides deploying EW.",
        "source": "Eurocontrol / NOTAM",
    },
    {
        "name": "Finnish / Russian Border Interference",
        "latitude": 64.0, "longitude": 28.0, "radius_km": 150,
        "severity": "medium", "type": "jamming",
        "description": "GPS interference near Finnish-Russian border, linked to Murmansk EW systems.",
        "source": "Finnish Transport Agency",
    },
    {
        "name": "Red Sea / Yemen GPS Interference",
        "latitude": 15.0, "longitude": 42.5, "radius_km": 200,
        "severity": "high", "type": "jamming",
        "description": "GPS jamming in Red Sea linked to Houthi anti-ship operations and coalition EW.",
        "source": "US NAVCENT",
    },
    {
        "name": "South China Sea GPS Spoofing",
        "latitude": 16.0, "longitude": 112.0, "radius_km": 200,
        "severity": "medium", "type": "spoofing",
        "description": "GPS spoofing incidents around disputed islands. PLA electronic warfare testing.",
        "source": "C4ADS / SkyTruth",
    },
    {
        "name": "Taiwan Strait GPS Interference",
        "latitude": 24.5, "longitude": 119.5, "radius_km": 100,
        "severity": "medium", "type": "spoofing",
        "description": "Intermittent GPS anomalies in Taiwan Strait during PLA exercises.",
        "source": "OPSGROUP",
    },
    {
        "name": "Korean DMZ Electronic Warfare",
        "latitude": 38.0, "longitude": 127.0, "radius_km": 80,
        "severity": "high", "type": "jamming",
        "description": "North Korean GPS jamming targeting South Korean military and civilian systems.",
        "source": "ROK MND / OPSGROUP",
    },
    {
        "name": "Libya Conflict EW Zone",
        "latitude": 32.5, "longitude": 13.5, "radius_km": 150,
        "severity": "medium", "type": "jamming",
        "description": "GPS jamming around Tripoli/Misrata. Multiple armed groups with EW capability.",
        "source": "UN Panel / Eurocontrol",
    },
]


class GPSJammingFetcher(BaseFetcher):
    """Fetches GPS/GNSS jamming zone data from known zones + GDELT news."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch GPS jamming data from known zones and GDELT news."""
        results: List[dict] = []

        # Start with known static zones (always available)
        for zone in _KNOWN_JAMMING_ZONES:
            results.append({
                "name": zone["name"],
                "latitude": zone["latitude"],
                "longitude": zone["longitude"],
                "radius_km": zone["radius_km"],
                "severity": zone["severity"],
                "type": zone["type"],
                "description": zone["description"],
                "source": zone["source"],
                "date": "ongoing",
                "verified": True,
            })

        # Augment with recent GDELT news about GPS jamming (non-blocking)
        try:
            import asyncio
            gdelt_zones = await asyncio.wait_for(
                self._fetch_gdelt_jamming(client), timeout=30.0,
            )
            # Deduplicate: skip GDELT results within ~200km of known zones
            for gz in gdelt_zones:
                too_close = False
                for known in _KNOWN_JAMMING_ZONES:
                    dlat = abs(gz["latitude"] - known["latitude"])
                    dlon = abs(gz["longitude"] - known["longitude"])
                    if dlat < 2 and dlon < 2:
                        too_close = True
                        break
                if not too_close:
                    results.append(gz)
        except asyncio.TimeoutError:
            logger.debug("GDELT GPS jamming search timed out, using static zones only")
        except Exception as exc:
            logger.debug("GDELT GPS jamming search failed: %s", exc)

        logger.info("GPS Jamming: %d zones (%d known + %d from news)",
                     len(results), len(_KNOWN_JAMMING_ZONES),
                     len(results) - len(_KNOWN_JAMMING_ZONES))
        return results

    async def _fetch_gdelt_jamming(self, client: httpx.AsyncClient) -> List[dict]:
        """Mine GDELT for recent GPS jamming/spoofing news."""
        results: List[dict] = []

        queries = [
            "GPS jamming OR GPS spoofing OR GNSS interference",
            "electronic warfare GPS OR navigation system disruption",
        ]

        for query in queries:
            try:
                features = await self._gdelt(client, query, timespan="14D", maxrows=50)
                for feat in features:
                    props = feat.get("properties", {}) if isinstance(feat, dict) else {}
                    geom = feat.get("geometry", {})
                    coords = geom.get("coordinates", [None, None])

                    if coords[0] is None or coords[1] is None:
                        continue

                    title = props.get("name", props.get("title", "GPS Interference"))
                    title_lower = title.lower()

                    if "spoofing" in title_lower or "spoof" in title_lower:
                        jam_type = "spoofing"
                    else:
                        jam_type = "jamming"

                    severity = "high" if any(w in title_lower for w in ["major", "severe", "widespread"]) else "medium"

                    results.append({
                        "name": title[:200],
                        "latitude": coords[1],
                        "longitude": coords[0],
                        "radius_km": 100,
                        "severity": severity,
                        "type": jam_type,
                        "description": title,
                        "source": props.get("source", "GDELT"),
                        "date": props.get("date", ""),
                        "verified": False,
                    })
            except Exception as exc:
                logger.debug("GDELT GPS query failed: %s", exc)

        return results
