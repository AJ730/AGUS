"""CBP Border Wait Times fetcher.

Fetches US-Mexico/Canada border crossing wait times.
Free, no authentication required.
URL: https://bwt.cbp.gov/api/bwtnew
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_BWT_URL = "https://bwt.cbp.gov/api/bwtnew"
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0)

# Known border crossing coordinates (port_number -> (lat, lon))
_PORT_COORDS: Dict[str, Tuple[float, float]] = {
    # Canadian Border
    "070801": (44.33, -75.89),   # Alexandria Bay
    "010401": (46.97, -67.84),   # Houlton
    "010101": (47.28, -68.62),   # Madawaska
    "010301": (47.04, -67.79),   # Fort Fairfield
    "040401": (44.71, -73.45),   # Champlain
    "020201": (44.79, -67.39),   # Calais
    "030601": (42.09, -76.81),   # Binghamton
    "040101": (44.99, -73.09),   # Derby Line
    "040901": (44.93, -74.72),   # Ogdensburg
    "041001": (44.87, -74.64),   # Massena
    "090101": (42.91, -78.90),   # Buffalo-Niagara
    "090204": (42.77, -78.89),   # Lewiston Bridge
    "090401": (43.25, -79.07),   # Lewiston Bridge
    "130102": (42.33, -83.05),   # Detroit Ambassador
    "130202": (42.31, -83.04),   # Detroit Tunnel
    "130301": (42.91, -82.43),   # Port Huron
    "240401": (46.77, -92.09),   # Duluth
    "240101": (48.72, -94.70),   # Int'l Falls
    "240301": (48.60, -93.41),   # Grand Portage
    "330101": (48.90, -97.15),   # Pembina
    "330201": (48.88, -97.31),   # Neche
    "330401": (48.99, -104.05),  # Portal
    "340201": (48.89, -105.54),  # Scobey
    "340301": (48.61, -109.39),  # Sweetgrass
    "360101": (49.00, -116.05),  # Eastport
    "360301": (48.78, -117.36),  # Boundary
    "301001": (48.79, -122.76),  # Blaine
    "301101": (48.99, -122.06),  # Sumas
    "301201": (48.96, -117.37),  # Oroville
    "301301": (48.11, -122.76),  # Anacortes
    "301401": (48.79, -122.76),  # Point Roberts
    # Mexican Border
    "260101": (32.55, -117.05),  # San Ysidro
    "260201": (32.58, -117.03),  # Otay Mesa
    "260301": (32.67, -115.50),  # Calexico
    "260401": (32.72, -114.72),  # Andrade
    "260601": (32.39, -114.95),  # Tecate
    "260701": (32.67, -115.50),  # Calexico East
    "250101": (32.32, -111.00),  # Nogales
    "250201": (31.33, -109.54),  # Douglas
    "250301": (31.73, -110.94),  # Naco
    "250401": (31.95, -112.05),  # Lukeville
    "250501": (31.96, -113.33),  # San Luis
    "240601": (31.76, -106.44),  # El Paso
    "240501": (29.57, -104.37),  # Presidio
    "230901": (27.50, -99.50),   # Laredo
    "231001": (28.70, -100.49),  # Eagle Pass
    "230301": (26.20, -98.32),   # Hidalgo
    "230201": (26.07, -97.50),   # Brownsville
    "230101": (26.21, -98.69),   # Roma
    "230401": (26.15, -97.69),   # Progreso
    "230501": (26.45, -98.73),   # Rio Grande City
    "230801": (27.77, -99.41),   # Columbia
}


class BorderWaitFetcher(BaseFetcher):
    """Fetches US border crossing wait times from CBP."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch all border wait times from CBP BWT API."""
        results: List[dict] = []
        try:
            resp = await client.get(
                _BWT_URL,
                timeout=_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            ports = data if isinstance(data, list) else data.get("port", [])

            for port in ports:
                name = port.get("port_name", "Unknown Port")
                crossing_name = port.get("crossing_name", "")
                border = port.get("border", "")
                port_num = port.get("port_number", "")

                # Look up coordinates from our static DB
                coords = _PORT_COORDS.get(port_num)
                if not coords:
                    continue
                lat, lon = coords

                # Parse wait times for passenger vehicles
                passenger = port.get("passenger_vehicle_lanes") or {}
                standard = passenger.get("standard_lanes") or {}
                wait_min_str = standard.get("delay_minutes")
                if not wait_min_str:
                    commercial = port.get("commercial_vehicle_lanes") or {}
                    std_comm = commercial.get("standard_lanes") or {}
                    wait_min_str = std_comm.get("delay_minutes")

                try:
                    wait_min = int(wait_min_str) if wait_min_str else -1
                except (ValueError, TypeError):
                    wait_min = -1

                status = port.get("port_status", "")
                wait_level = (
                    "Closed" if status.lower() == "closed" or wait_min < 0
                    else "Short" if wait_min < 30
                    else "Moderate" if wait_min < 60
                    else "Long" if wait_min < 120
                    else "Very Long"
                )

                full_name = f"{name} — {crossing_name}" if crossing_name else name
                results.append({
                    "name": full_name,
                    "latitude": lat,
                    "longitude": lon,
                    "border": border,
                    "wait_minutes": wait_min,
                    "wait_level": wait_level,
                    "lanes_open": standard.get("lanes_open", ""),
                    "port_status": status,
                    "date": port.get("date", ""),
                    "source": "CBP BWT",
                })

            logger.info("BorderWait: %d crossings", len(results))
        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
            logger.warning("BorderWait fetch failed: %s", exc)

        return results
