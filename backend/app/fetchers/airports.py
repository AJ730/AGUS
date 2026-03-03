"""OurAirports CSV airport data fetcher."""

from __future__ import annotations

import csv
import io
import logging
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"


class AirportFetcher(BaseFetcher):
    """Fetches large and medium airports from OurAirports CSV data."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        try:
            resp = await client.get(
                _URL,
                timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
            )
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            results: List[dict] = []
            for row in reader:
                apt_type = row.get("type", "")
                if apt_type not in ("large_airport", "medium_airport"):
                    continue
                try:
                    lat = float(row.get("latitude_deg", 0))
                    lon = float(row.get("longitude_deg", 0))
                except (ValueError, TypeError):
                    continue
                elev_str = row.get("elevation_ft", "0") or "0"
                try:
                    elevation = int(float(elev_str))
                except (ValueError, TypeError):
                    elevation = 0
                ident = row.get("ident", "")
                results.append({
                    "icao_code": ident,
                    "iata_code": row.get("iata_code", ""),
                    "name": row.get("name", ""),
                    "city": row.get("municipality", ""),
                    "country": row.get("iso_country", ""),
                    "latitude": lat, "longitude": lon,
                    "elevation": elevation, "type": apt_type,
                    "liveatc_url": f"https://www.liveatc.net/listen/{ident.lower()}" if ident else "",
                })
            return results
        except Exception as exc:
            logger.warning("OurAirports fetch failed: %s", exc)
        return []
