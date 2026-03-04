"""NOAA Space Weather Prediction Center fetcher.

Fetches Kp index, solar flares, and geomagnetic storm data from SWPC.
Free, no authentication required.
URL: https://services.swpc.noaa.gov/json/
"""

from __future__ import annotations

import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_SWPC_BASE = "https://services.swpc.noaa.gov"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)

# Aurora oval approximate center points for visualization
_AURORA_POINTS = [
    {"name": "Aurora (N. Scandinavia)", "latitude": 68.0, "longitude": 20.0},
    {"name": "Aurora (N. Canada)", "latitude": 64.0, "longitude": -100.0},
    {"name": "Aurora (Iceland)", "latitude": 65.0, "longitude": -18.0},
    {"name": "Aurora (Alaska)", "latitude": 65.0, "longitude": -150.0},
    {"name": "Aurora (N. Russia)", "latitude": 67.0, "longitude": 60.0},
    {"name": "Aurora (S. Australia)", "latitude": -65.0, "longitude": 140.0},
    {"name": "Aurora (S. Atlantic)", "latitude": -60.0, "longitude": -30.0},
]


class SpaceWeatherFetcher(BaseFetcher):
    """Fetches space weather data from NOAA SWPC."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch Kp index, solar flares, and geomagnetic storms."""
        return await self._collect(
            client,
            self._fetch_kp_index,
            self._fetch_xray_flux,
            self._fetch_geomag_storms,
        )

    async def _fetch_kp_index(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch planetary Kp index (current + forecast)."""
        results: List[dict] = []
        try:
            resp = await client.get(
                f"{_SWPC_BASE}/products/noaa-planetary-k-index.json",
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data or len(data) < 2:
                return []

            # Latest Kp entry (skip header row)
            latest = data[-1]
            kp_val = float(latest[1]) if latest[1] else 0
            kp_level = (
                "Extreme (G5)" if kp_val >= 9
                else "Severe (G4)" if kp_val >= 8
                else "Strong (G3)" if kp_val >= 7
                else "Moderate (G2)" if kp_val >= 6
                else "Minor (G1)" if kp_val >= 5
                else "Active" if kp_val >= 4
                else "Quiet"
            )

            # Place Kp gauge at auroral zone points
            for pt in _AURORA_POINTS:
                results.append({
                    "name": f"Kp={kp_val:.1f} — {kp_level}",
                    "latitude": pt["latitude"],
                    "longitude": pt["longitude"],
                    "category": "kp_index",
                    "severity": kp_level,
                    "kp_value": kp_val,
                    "date": latest[0] if latest[0] else "",
                    "source": "NOAA SWPC",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("SpaceWeather Kp fetch failed: %s", exc)
        return results

    async def _fetch_xray_flux(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch GOES X-ray flux data (solar flare indicator)."""
        results: List[dict] = []
        try:
            resp = await client.get(
                f"{_SWPC_BASE}/json/goes/primary/xrays-6-hour.json",
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return []

            # Get latest X-ray reading
            latest = data[-1] if data else {}
            flux = latest.get("flux", 0)
            energy = latest.get("energy", "")

            # Classify X-ray flux into flare class
            try:
                flux_val = float(flux)
                flare_class = (
                    "X-class (Extreme)" if flux_val >= 1e-4
                    else "M-class (Strong)" if flux_val >= 1e-5
                    else "C-class (Moderate)" if flux_val >= 1e-6
                    else "B-class (Low)" if flux_val >= 1e-7
                    else "A-class (Quiet)"
                )
            except (ValueError, TypeError):
                flux_val = 0
                flare_class = "Unknown"

            # Place at sun-side points
            results.append({
                "name": f"X-Ray Flux: {flare_class}",
                "latitude": 0.0,
                "longitude": 0.0,
                "category": "xray_flux",
                "severity": flare_class,
                "date": latest.get("time_tag", ""),
                "source": "NOAA SWPC GOES",
            })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("SpaceWeather X-ray fetch failed: %s", exc)
        return results

    async def _fetch_geomag_storms(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch geomagnetic storm data from Kp predictions."""
        # Already handled by _fetch_kp_index; this fetches the 3-day forecast
        results: List[dict] = []
        try:
            resp = await client.get(
                f"{_SWPC_BASE}/products/noaa-planetary-k-index-forecast.json",
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            for entry in data[:10]:
                kp = entry.get("kp")
                if kp is None:
                    continue
                try:
                    kp_val = float(kp)
                except (ValueError, TypeError):
                    continue
                if kp_val < 5:
                    continue  # Only report storm-level predictions
                results.append({
                    "name": f"Geomagnetic Storm Forecast Kp={kp_val}",
                    "latitude": 65.0,
                    "longitude": 0.0,
                    "category": "geomagnetic_storm",
                    "severity": "G" + str(min(5, int(kp_val) - 4)),
                    "kp_value": kp_val,
                    "date": entry.get("time_tag", ""),
                    "source": "NOAA SWPC",
                })
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("SpaceWeather geomag forecast failed: %s", exc)
        return results
