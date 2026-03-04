"""SondeHub radiosonde (weather balloon) fetcher.

Fetches real-time weather balloon positions from SondeHub.
Free, no authentication required.
URL: https://api.v2.sondehub.org/sondes
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_SONDEHUB_URL = "https://api.v2.sondehub.org/sondes"
_TIMEOUT = httpx.Timeout(connect=10.0, read=45.0, write=5.0, pool=10.0)


class RadiosondeFetcher(BaseFetcher):
    """Fetches real-time weather balloon data from SondeHub."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch active radiosondes from SondeHub API."""
        results: List[dict] = []
        try:
            resp = await client.get(
                _SONDEHUB_URL,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            # SondeHub returns a dict keyed by serial number
            if not isinstance(data, dict):
                return []

            for serial, sonde in list(data.items())[:500]:
                lat = sonde.get("lat")
                lon = sonde.get("lon")
                if lat is None or lon is None:
                    continue

                alt = sonde.get("alt", 0) or 0
                vel_v = sonde.get("vel_v", 0) or 0
                phase = "Ascending" if vel_v > 0 else "Descending" if vel_v < 0 else "Float"
                temp = sonde.get("temp")
                freq = sonde.get("frequency")
                sonde_type = sonde.get("type", "Unknown")

                results.append({
                    "name": f"Sonde {serial}",
                    "serial": serial,
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "altitude": float(alt),
                    "vertical_rate": vel_v,
                    "phase": phase,
                    "temperature": temp,
                    "frequency": f"{freq} MHz" if freq else "",
                    "sonde_type": sonde_type,
                    "heading": sonde.get("heading"),
                    "source": "SondeHub",
                })

            logger.info("Radiosondes: %d active sondes", len(results))
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Radiosonde fetch failed: %s", exc)

        return results
