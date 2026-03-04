"""NASA JPL Close Approach Data (CAD) fetcher.

Fetches near-Earth objects approaching within 0.05 AU in the next 60 days.
Free, no authentication required.
URL: https://ssd-api.jpl.nasa.gov/cad.api
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_CAD_URL = "https://ssd-api.jpl.nasa.gov/cad.api"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)


class AsteroidFetcher(BaseFetcher):
    """Fetches near-Earth asteroid close approach data from NASA JPL."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch asteroid close approach data for next 60 days."""
        results: List[dict] = []
        now = datetime.now(timezone.utc)
        date_min = now.strftime("%Y-%m-%d")
        date_max = (now + timedelta(days=60)).strftime("%Y-%m-%d")

        try:
            resp = await client.get(
                _CAD_URL,
                params={
                    "date-min": date_min,
                    "date-max": date_max,
                    "dist-max": "0.05",
                    "sort": "dist",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            fields = data.get("fields", [])
            rows = data.get("data", [])

            # Build field index map
            idx = {f: i for i, f in enumerate(fields)}

            for row in rows[:100]:
                des = row[idx.get("des", 0)] if "des" in idx else "Unknown"
                cd = row[idx.get("cd", 1)] if "cd" in idx else ""
                dist = row[idx.get("dist", 2)] if "dist" in idx else ""
                dist_min = row[idx.get("dist_min", 3)] if "dist_min" in idx else ""
                v_rel = row[idx.get("v_rel", 4)] if "v_rel" in idx else ""
                h = row[idx.get("h", 5)] if "h" in idx else ""

                # Estimate size from absolute magnitude H
                try:
                    h_val = float(h)
                    # Rough diameter estimate in meters: D ≈ 1329 * 10^(-H/5) / sqrt(albedo)
                    # Assume albedo = 0.15
                    diameter_m = 1329000 * (10 ** (-h_val / 5)) / (0.15 ** 0.5)
                    size_str = (
                        f"{diameter_m:.0f} m" if diameter_m >= 1
                        else f"{diameter_m * 100:.1f} cm"
                    )
                except (ValueError, TypeError):
                    diameter_m = 0
                    size_str = "Unknown"

                try:
                    dist_au = float(dist)
                    dist_ld = dist_au * 389.17  # AU to lunar distances
                except (ValueError, TypeError):
                    dist_au = 0
                    dist_ld = 0

                # Threat level based on distance + size
                threat = (
                    "HIGH" if dist_au < 0.01 and diameter_m > 50
                    else "MODERATE" if dist_au < 0.02
                    else "LOW"
                )

                results.append({
                    "name": f"Asteroid {des}",
                    "designation": des,
                    "close_approach_date": cd,
                    "distance_au": dist_au,
                    "distance_ld": round(dist_ld, 2),
                    "distance_min_au": dist_min,
                    "velocity_km_s": v_rel,
                    "absolute_magnitude": h,
                    "estimated_diameter": size_str,
                    "threat_level": threat,
                    "latitude": 0.0,
                    "longitude": 0.0,
                    "source": "NASA JPL CAD",
                })

            logger.info("Asteroids: %d close approaches in next 60 days", len(results))
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("Asteroid fetch failed: %s", exc)

        return results
