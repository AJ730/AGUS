"""Satellite position fetcher from SatNOGS TLE data."""

from __future__ import annotations

import logging
import math
from typing import List, Optional

import httpx

from ..config import MAX_SATELLITES, MAX_STARLINK
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_SAT_TYPES = {
    "space_station": "ISS ZARYA TIANHE CSS", "military": "COSMOS KOSMOS",
    "navigation": "GPS NAVSTAR GLONASS BEIDOU COMPASS GALILEO",
    "communications": "STARLINK ONEWEB IRIDIUM INTELSAT INMARSAT SES",
    "weather": "GOES METOP NOAA METEOR FENGYUN",
    "earth_observation": "LANDSAT SENTINEL WORLDVIEW",
    "science": "HUBBLE JWST CHANDRA",
}


def _derive_type(name: str) -> str:
    upper = name.upper()
    for sat_type, kws in _SAT_TYPES.items():
        if any(kw in upper for kw in kws.split()):
            return sat_type
    return "reconnaissance" if (upper.startswith("USA-") or "NROL" in upper) else "other"


def _tle_to_position(line2: str) -> Optional[dict]:
    try:
        inclination = float(line2[8:16].strip())
        ra_node = float(line2[17:25].strip())
        mean_anomaly = float(line2[43:51].strip())
        mean_motion = float(line2[52:63].strip())
        ma_rad = math.radians(mean_anomaly)
        lat = inclination * math.sin(ma_rad)
        lon = (ra_node + mean_anomaly - 180.0) % 360.0 - 180.0
        period_min = 1440.0 / mean_motion if mean_motion else 90.0
        alt_km = (
            ((period_min * 60) ** 2 * 3.986e14 / (4 * math.pi ** 2)) ** (1 / 3)
            / 1000 - 6371
        )
        velocity = round(7.91 * (6371 / (6371 + max(alt_km, 0))) ** 0.5, 2)
        return {"latitude": round(lat, 4), "longitude": round(lon, 4),
                "altitude": round(max(alt_km, 0), 2), "velocity": velocity}
    except (ValueError, IndexError):
        return None


class SatelliteFetcher(BaseFetcher):
    """Fetches satellite positions from ISS API and SatNOGS TLE data."""

    async def _from_iss(self, client: httpx.AsyncClient) -> List[dict]:
        resp = await client.get(
            "https://api.wheretheiss.at/v1/satellites/25544", timeout=10.0,
        )
        resp.raise_for_status()
        iss = resp.json()
        return [{
            "name": "ISS (ZARYA)", "norad_id": 25544,
            "latitude": iss.get("latitude"), "longitude": iss.get("longitude"),
            "altitude": iss.get("altitude"), "velocity": iss.get("velocity"),
            "type": "space_station",
        }]

    async def _from_satnogs(self, client: httpx.AsyncClient) -> List[dict]:
        resp = await client.get(
            "https://db.satnogs.org/api/tle/",
            params={"format": "json", "satellite__status": "alive"},
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=5.0, pool=10.0),
        )
        resp.raise_for_status()
        results, seen, starlink_count = [], {"ISS (ZARYA)"}, 0
        for entry in resp.json():
            if len(results) >= MAX_SATELLITES:
                break
            tle2 = entry.get("tle2", "").strip()
            if not entry.get("tle1", "").strip() or not tle2:
                continue
            name = (entry.get("tle0", "").lstrip("0 ").strip()) or "Unknown"
            if name in seen:
                continue
            if "STARLINK" in name.upper():
                if starlink_count >= MAX_STARLINK:
                    continue
                starlink_count += 1
            pos = _tle_to_position(tle2)
            if not pos:
                continue
            seen.add(name)
            results.append({
                "name": name, "norad_id": entry.get("norad_cat_id", 0),
                "type": _derive_type(name), **pos,
            })
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._collect(client, self._from_iss, self._from_satnogs)
