"""Satellite correlation engine — cross-references satellite passes with conflict zones."""

from __future__ import annotations

import logging
import math
from typing import List

logger = logging.getLogger("agus.sat_analysis")

# Known military/reconnaissance satellite prefixes (NORAD catalog)
RECON_SATELLITES = {
    "USA": "US Military/NRO",
    "NROL": "NRO Launch",
    "LACROSSE": "US SAR Reconnaissance",
    "ONYX": "US SAR Reconnaissance",
    "KEYHOLE": "US Optical Reconnaissance",
    "MISTY": "US Stealth Satellite",
    "COSMOS": "Russian Military",
    "KOSMOS": "Russian Military",
    "KONDOR": "Russian SAR",
    "BARS": "Russian Optical",
    "PERSONA": "Russian ELINT",
    "LOTOS": "Russian SIGINT",
    "YAOGAN": "Chinese Military Reconnaissance",
    "GAOFEN": "Chinese Earth Observation",
    "JILIN": "Chinese Commercial/Military",
    "ZHANGHENG": "Chinese Electromagnetic",
    "OFEK": "Israeli Reconnaissance",
    "EROS": "Israeli Commercial/Military",
    "SAR-LUPE": "German SAR Reconnaissance",
    "HELIOS": "French Optical Reconnaissance",
    "PLEIADES": "French High-Res Optical",
    "CSO": "French Military Optical",
    "IGS": "Japanese Intelligence",
}

# Active conflict zones for correlation
CONFLICT_ZONES = [
    {"name": "Ukraine", "lat": 48.5, "lon": 35.0, "radius_km": 500},
    {"name": "Gaza/Israel", "lat": 31.5, "lon": 34.5, "radius_km": 200},
    {"name": "Iran", "lat": 32.4, "lon": 53.7, "radius_km": 600},
    {"name": "Syria", "lat": 35.0, "lon": 38.0, "radius_km": 300},
    {"name": "Yemen/Red Sea", "lat": 15.5, "lon": 43.0, "radius_km": 400},
    {"name": "Sudan", "lat": 15.6, "lon": 32.5, "radius_km": 400},
    {"name": "Taiwan Strait", "lat": 24.0, "lon": 119.0, "radius_km": 300},
    {"name": "Korean Peninsula", "lat": 38.0, "lon": 127.0, "radius_km": 250},
    {"name": "South China Sea", "lat": 14.0, "lon": 115.0, "radius_km": 500},
    {"name": "Eastern Mediterranean", "lat": 35.0, "lon": 30.0, "radius_km": 400},
    {"name": "Persian Gulf", "lat": 26.0, "lon": 52.0, "radius_km": 300},
    {"name": "Horn of Africa", "lat": 5.0, "lon": 45.0, "radius_km": 400},
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def classify_satellite(name: str) -> str | None:
    """Classify a satellite as military/recon if it matches known prefixes."""
    name_upper = (name or "").upper()
    for prefix, classification in RECON_SATELLITES.items():
        if prefix in name_upper:
            return classification
    return None


def correlate_with_conflicts(satellites: List[dict], conflicts: List[dict] | None = None) -> dict:
    """Cross-reference satellite positions with conflict zones.

    Returns structured intelligence about military satellite activity over hotspots.
    """
    correlations = []
    recon_count = 0
    zone_activity: dict[str, list] = {}

    for sat in satellites:
        name = sat.get("name", "")
        lat = sat.get("latitude", sat.get("lat"))
        lon = sat.get("longitude", sat.get("lon"))
        if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
            continue

        classification = classify_satellite(name)
        if classification:
            recon_count += 1

        # Check proximity to conflict zones
        for zone in CONFLICT_ZONES:
            dist = _haversine_km(lat, lon, zone["lat"], zone["lon"])
            if dist <= zone["radius_km"]:
                entry = {
                    "satellite": name,
                    "zone": zone["name"],
                    "distance_km": round(dist),
                    "is_military": classification is not None,
                    "classification": classification or "Civilian/Unknown",
                    "altitude_km": sat.get("altitude", sat.get("alt", 0)),
                }
                correlations.append(entry)
                zone_activity.setdefault(zone["name"], []).append(entry)

    # Build summary
    summary_lines = []
    if correlations:
        summary_lines.append(f"Detected {len(correlations)} satellite passes over conflict zones.")
        summary_lines.append(f"Military/reconnaissance satellites tracked: {recon_count}")
        for zone_name, sats in sorted(zone_activity.items(), key=lambda x: -len(x[1])):
            mil_sats = [s for s in sats if s["is_military"]]
            summary_lines.append(
                f"  {zone_name}: {len(sats)} satellites overhead "
                f"({len(mil_sats)} military/recon)"
            )
    else:
        summary_lines.append("No satellite passes currently detected over active conflict zones.")

    return {
        "correlations": correlations[:50],
        "zone_activity": {k: len(v) for k, v in zone_activity.items()},
        "recon_satellite_count": recon_count,
        "total_passes": len(correlations),
        "summary": "\n".join(summary_lines),
    }
