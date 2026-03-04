"""Intelligence endpoints: correlate, analyze, predict, missile_tests."""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..cache import CacheManager
from ..fetchers.sat_analysis import correlate_with_conflicts
from .. import llm
from ._helpers import _cache, _client, _fetcher_fns, get_cached_items

logger = logging.getLogger("agus.routes")

router = APIRouter()

# ---------------------------------------------------------------------------
# Strike-related constants for mining Reddit/Telegram OSINT
# ---------------------------------------------------------------------------

_STRIKE_KEYWORDS = {
    "missile", "airstrike", "air strike", "drone strike", "shelling",
    "bombing", "ballistic", "cruise missile", "icbm", "rocket attack",
    "artillery", "mortar", "rpg", "himars", "atacms", "storm shadow",
    "scalp", "iskander", "shahed", "caliber", "kalibr", "s-300", "s-400",
    "patriot", "iron dome", "thaad", "intercepted", "shot down",
    "explosion", "detonation", "strike on", "struck", "hit by",
    "bombardment", "barrage", "salvo", "launched", "fired upon",
    "drone attack", "kamikaze drone", "fpv drone", "loitering munition",
    "cruise", "warhead", "payload", "impact", "crater",
}

_TYPE_INFERENCE = [
    ({"missile", "ballistic", "icbm", "cruise missile", "iskander", "kalibr", "caliber", "atacms"}, "missile_strike"),
    ({"drone", "shahed", "kamikaze drone", "fpv drone", "loitering munition"}, "drone_strike"),
    ({"airstrike", "air strike", "storm shadow", "scalp"}, "airstrike"),
    ({"shelling", "artillery", "mortar", "himars", "barrage", "salvo"}, "shelling"),
    ({"bombing", "bomb", "detonation", "ied"}, "bombing"),
    ({"intercepted", "shot down", "iron dome", "patriot", "s-300", "s-400", "thaad"}, "interception"),
]


def _extract_osint_strikes(cache: CacheManager) -> list:
    """Mine cached Reddit + Telegram OSINT for missile/strike/attack reports.

    Scans post titles for strike-related keywords and converts
    matching geolocated posts into missile_tests-compatible events.

    Args:
        cache: CacheManager to read reddit_osint and telegram_osint slots from.

    Returns:
        List of strike events in missile_tests format.
    """
    results = []

    for layer_name, source_label in [("reddit_osint", "Reddit"), ("telegram_osint", "Telegram")]:
        items = get_cached_items(cache, layer_name)
        for item in items:
            title = (item.get("title") or "").lower()
            if not title:
                continue

            matched_keywords = [kw for kw in _STRIKE_KEYWORDS if kw in title]
            if not matched_keywords:
                continue

            lat = item.get("latitude")
            lon = item.get("longitude")
            if lat is None or lon is None:
                continue

            # Infer event type from keywords
            event_type = "explosion"
            for kw_set, etype in _TYPE_INFERENCE:
                if any(kw in title for kw in kw_set):
                    event_type = etype
                    break

            score = item.get("score", 0)
            comments = item.get("comments", 0)
            existing_severity = item.get("severity", "")
            if score > 5000 or comments > 500 or existing_severity == "critical":
                fatalities_estimate = 10
            elif score > 1000 or existing_severity == "high":
                fatalities_estimate = 5
            else:
                fatalities_estimate = 0

            channel = item.get("channel", item.get("source", ""))
            results.append({
                "name": item.get("title", f"{source_label} Strike Report")[:200],
                "date": item.get("date", ""),
                "country": item.get("location", ""),
                "region": item.get("location", ""),
                "latitude": lat,
                "longitude": lon,
                "type": event_type,
                "sub_type": ", ".join(matched_keywords[:3]),
                "actor": "",
                "target": "",
                "fatalities": fatalities_estimate,
                "source": f"{source_label} {channel}",
                "url": item.get("url", ""),
            })

    return results


@router.get("/missile_tests")
async def missile_tests(request: Request):
    """Missile/strike data enhanced with Reddit OSINT cross-reference."""
    cache = _cache(request)
    fns = _fetcher_fns(request)

    base_data = await cache.get("missile_tests", fns["missile_tests"])
    reddit_strikes = _extract_osint_strikes(cache)

    if reddit_strikes:
        existing_coords = set()
        if isinstance(base_data, list):
            for item in base_data:
                lat = item.get("latitude")
                lon = item.get("longitude")
                if lat is not None and lon is not None:
                    existing_coords.add((round(float(lat), 1), round(float(lon), 1)))

        new_strikes = []
        for rs in reddit_strikes:
            key = (round(rs["latitude"], 1), round(rs["longitude"], 1))
            if key not in existing_coords:
                new_strikes.append(rs)
                existing_coords.add(key)

        if isinstance(base_data, list):
            base_data = base_data + new_strikes
        else:
            base_data = new_strikes

        logger.info("Missile layer enhanced: +%d strike reports from Reddit", len(new_strikes))

    return JSONResponse(
        content=base_data,
        headers={"X-Cache-Fresh": str(cache.slot("missile_tests").is_fresh).lower()},
    )


# ---------------------------------------------------------------------------
# Correlation Analysis
# ---------------------------------------------------------------------------

@router.get("/correlate")
async def correlate(request: Request):
    """Cross-reference all OSINT layers for intelligence correlation."""
    cache = _cache(request)

    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _extract_coords(item: dict) -> tuple:
        lat = item.get("latitude") or item.get("lat")
        lon = item.get("longitude") or item.get("lon") or item.get("lng")
        try:
            return float(lat), float(lon)
        except (TypeError, ValueError):
            return None, None

    conflicts = get_cached_items(cache, "conflicts")
    missiles = get_cached_items(cache, "missile_tests")
    mil_bases = get_cached_items(cache, "military_bases")
    threat_intel = get_cached_items(cache, "threat_intel")
    telegram = get_cached_items(cache, "telegram_osint")
    reddit = get_cached_items(cache, "reddit_osint")
    carriers = get_cached_items(cache, "carriers")
    cyber = get_cached_items(cache, "cyber")

    correlations = []

    # 1. Conflicts near military bases (within 200km)
    for conflict in conflicts[:200]:
        clat, clon = _extract_coords(conflict)
        if clat is None:
            continue
        for base in mil_bases[:200]:
            blat, blon = _extract_coords(base)
            if blat is None:
                continue
            dist = _haversine_km(clat, clon, blat, blon)
            if dist < 200:
                correlations.append({
                    "type": "conflict_near_base",
                    "severity": "high",
                    "distance_km": round(dist),
                    "conflict": conflict.get("event_type", "Conflict"),
                    "conflict_country": conflict.get("country", ""),
                    "base_name": base.get("name", "Military Base"),
                    "base_operator": base.get("operator", ""),
                    "latitude": clat,
                    "longitude": clon,
                })

    # 2. Missile strikes near carriers (within 500km)
    for missile in missiles[:100]:
        mlat, mlon = _extract_coords(missile)
        if mlat is None:
            continue
        for carrier in carriers[:20]:
            klat, klon = _extract_coords(carrier)
            if klat is None:
                continue
            dist = _haversine_km(mlat, mlon, klat, klon)
            if dist < 500:
                correlations.append({
                    "type": "strike_near_carrier",
                    "severity": "critical",
                    "distance_km": round(dist),
                    "strike_type": missile.get("type", "Strike"),
                    "carrier_name": carrier.get("name", "Carrier"),
                    "carrier_operator": carrier.get("operator", ""),
                    "latitude": mlat,
                    "longitude": mlon,
                })

    # 3. Cyber threats targeting conflict zone countries
    conflict_countries = set()
    for c in conflicts[:500]:
        cc = (c.get("country") or "").strip()
        if cc:
            conflict_countries.add(cc.lower())

    for threat in threat_intel[:200]:
        tc = (threat.get("country") or "").strip().lower()
        if tc and tc in conflict_countries:
            correlations.append({
                "type": "cyber_targets_conflict_zone",
                "severity": threat.get("severity", "medium"),
                "threat_title": threat.get("title", ""),
                "country": threat.get("country", ""),
                "indicator": threat.get("indicator", ""),
                "latitude": threat.get("latitude"),
                "longitude": threat.get("longitude"),
            })

    # 4. OSINT corroboration
    conflict_locations = set()
    for c in conflicts[:300]:
        loc = (c.get("location") or c.get("country") or "").lower()
        if loc:
            conflict_locations.add(loc)

    for osint in (telegram + reddit)[:300]:
        loc = (osint.get("location") or "").lower()
        if loc and loc in conflict_locations:
            correlations.append({
                "type": "osint_corroborates_conflict",
                "severity": osint.get("severity", "medium"),
                "osint_title": osint.get("title", "")[:100],
                "osint_source": osint.get("source", ""),
                "location": osint.get("location", ""),
                "latitude": osint.get("latitude"),
                "longitude": osint.get("longitude"),
            })

    summary = {
        "total_correlations": len(correlations),
        "conflicts_near_bases": len([c for c in correlations if c["type"] == "conflict_near_base"]),
        "strikes_near_carriers": len([c for c in correlations if c["type"] == "strike_near_carrier"]),
        "cyber_conflict_zones": len([c for c in correlations if c["type"] == "cyber_targets_conflict_zone"]),
        "osint_corroborations": len([c for c in correlations if c["type"] == "osint_corroborates_conflict"]),
        "layer_counts": {
            "conflicts": len(conflicts),
            "missiles": len(missiles),
            "military_bases": len(mil_bases),
            "threat_intel": len(threat_intel),
            "telegram_osint": len(telegram),
            "reddit_osint": len(reddit),
            "carriers": len(carriers),
            "cyber": len(cyber),
        },
    }

    return JSONResponse(content={
        "correlations": correlations[:500],
        "summary": summary,
    })


# ---------------------------------------------------------------------------
# LLM Intelligence Analysis
# ---------------------------------------------------------------------------

@router.post("/analyze")
async def analyze(request: Request):
    """AI-powered intelligence analysis using Azure OpenAI."""
    try:
        body = await request.json()
    except (ValueError, KeyError):
        body = {}

    cache = _cache(request)
    events_summary_parts = []

    for layer_name in ["conflicts", "missile_tests", "threat_intel", "rocket_alerts", "telegram_osint", "reddit_osint", "cyber"]:
        try:
            slot = cache.slot(layer_name)
        except KeyError:
            continue
        if slot and slot.entry.data:
            data = slot.entry.data
            items = data if isinstance(data, list) else (
                data.get("data") or data.get("events") or data.get("results") or []
            )
            count = len(items) if isinstance(items, list) else 0
            events_summary_parts.append(f"{layer_name}: {count} events")

    satellite_data = ""
    try:
        sat_slot = cache.slot("satellites")
    except KeyError:
        sat_slot = None
    if sat_slot and sat_slot.entry.data:
        sat_items = sat_slot.entry.data if isinstance(sat_slot.entry.data, list) else []
        if sat_items:
            correlation = correlate_with_conflicts(sat_items)
            satellite_data = correlation.get("summary", "")

    context = {
        **body,
        "events_summary": "\n".join(events_summary_parts),
        "satellite_data": satellite_data,
    }

    client = _client(request)
    result = await llm.analyze(context, client)
    if satellite_data:
        result["satellite_intel"] = satellite_data
    return JSONResponse(content=result)


@router.get("/predict")
async def predict(request: Request):
    """Satellite-driven predictions — correlate orbital data with conflict zones."""
    cache = _cache(request)
    try:
        sat_slot = cache.slot("satellites")
    except KeyError:
        sat_slot = None
    sat_items = []
    if sat_slot and sat_slot.entry.data:
        sat_items = sat_slot.entry.data if isinstance(sat_slot.entry.data, list) else []

    correlation = correlate_with_conflicts(sat_items)

    if llm.is_configured():
        client = _client(request)
        context = {
            "region": "Global Conflict Zones",
            "layers": ["satellites"],
            "satellite_data": correlation.get("summary", ""),
            "events_summary": f"Satellite passes: {correlation['total_passes']}, Military/recon: {correlation['recon_satellite_count']}",
        }
        llm_result = await llm.analyze(context, client)
        correlation["ai_analysis"] = llm_result.get("briefing", "")
        correlation["predictions"] = llm_result.get("predictions", [])

    return JSONResponse(content=correlation)
