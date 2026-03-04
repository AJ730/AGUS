"""
Agus OSINT Backend -- API Routes
=====================================
All API endpoints as a FastAPI router.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .cache import CacheEntry, CacheManager
from .flight_intel import FlightIntelligence
from . import llm
from .fetchers.sat_analysis import correlate_with_conflicts

logger = logging.getLogger("agus.routes")

router = APIRouter(prefix="/api")

# These will be injected by the server module via app.state
# Accessed at runtime through request.app.state


def _cache(request: Request) -> CacheManager:
    return request.app.state.cache_manager


def _client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def _fetcher_fns(request: Request) -> dict:
    return request.app.state.fetcher_fns


def _intel(request: Request) -> FlightIntelligence:
    return request.app.state.flight_intel


# Per-icao24 flight detail cache
_flight_detail_cache: Dict[str, CacheEntry] = {}
_flight_detail_locks: Dict[str, asyncio.Lock] = {}
_FLIGHT_DETAIL_TTL = 15.0


# ---------------------------------------------------------------------------
# Health & sources
# ---------------------------------------------------------------------------

@router.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": _cache(request).status(),
    }


@router.get("/sources")
async def sources(request: Request):
    return _cache(request).sources_list()


# ---------------------------------------------------------------------------
# Generic layer endpoint helper
# ---------------------------------------------------------------------------

async def _layer_response(request: Request, name: str) -> JSONResponse:
    cache = _cache(request)
    fns = _fetcher_fns(request)
    data = await cache.get(name, fns[name])
    return JSONResponse(
        content=data,
        headers={"X-Cache-Fresh": str(cache.slot(name).is_fresh).lower()},
    )


# ---------------------------------------------------------------------------
# Data endpoints
# ---------------------------------------------------------------------------

@router.get("/flights")
async def flights(request: Request):
    return await _layer_response(request, "flights")


@router.get("/flights_viewport")
async def flights_viewport(request: Request, lat: float = 0, lon: float = 0, dist: int = 250):
    """On-demand flight fetch for the user's current map viewport.

    Queries ADS-B APIs for the specific region the user is looking at,
    merges with cached global flights, and returns the combined result.
    This ensures precise coverage where the user is actually looking.

    Args:
        lat: Viewport center latitude.
        lon: Viewport center longitude.
        dist: Radius in nautical miles (max 250).
    """
    import time as _time
    from .fetchers.flights import _ADSB_SOURCES, FlightFetcher

    dist = min(dist, 250)
    cache = _cache(request)
    intel = _intel(request)

    # Get cached global flights as base
    fns = _fetcher_fns(request)
    base_data = await cache.get("flights", fns["flights"])
    base_flights = base_data if isinstance(base_data, list) else []

    # Build index of existing icao24s
    existing = {f.get("icao24"): f for f in base_flights if f.get("icao24")}

    # Fetch viewport-specific flights from ADS-B sources
    fetcher = FlightFetcher(intel)
    new_count = 0
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=8.0, read=15.0, write=5.0, pool=10.0),
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        },
    ) as vp_client:
        seen: set = set(existing.keys())
        for src_name, base_url, style in _ADSB_SOURCES:
            try:
                url = FlightFetcher._build_url(base_url, style, lat, lon, dist)
                resp = await vp_client.get(url)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for ac in data.get("ac") or data.get("aircraft") or []:
                    enriched = fetcher._enrich_adsb(ac, seen)
                    if enriched and enriched["icao24"] not in existing:
                        existing[enriched["icao24"]] = enriched
                        new_count += 1
                break  # one success is enough
            except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError):
                continue

    result = list(existing.values())
    logger.info("Viewport fetch (%.1f,%.1f r=%dnm): +%d new, %d total",
                lat, lon, dist, new_count, len(result))
    return JSONResponse(content=result)


@router.get("/conflicts")
async def conflicts(request: Request):
    return await _layer_response(request, "conflicts")


@router.get("/events")
async def events(request: Request):
    return await _layer_response(request, "events")


@router.get("/fires")
async def fires(request: Request):
    return await _layer_response(request, "fires")


@router.get("/vessels")
async def vessels(request: Request):
    return await _layer_response(request, "vessels")


@router.get("/cctv")
async def cctv(request: Request):
    return await _layer_response(request, "cctv")


@router.get("/satellites")
async def satellites(request: Request):
    return await _layer_response(request, "satellites")


@router.get("/earthquakes")
async def earthquakes(request: Request):
    return await _layer_response(request, "earthquakes")


@router.get("/nuclear")
async def nuclear(request: Request):
    return await _layer_response(request, "nuclear")


@router.get("/weather_alerts")
async def weather_alerts(request: Request):
    return await _layer_response(request, "weather_alerts")


@router.get("/terrorism")
async def terrorism(request: Request):
    return await _layer_response(request, "terrorism")


@router.get("/refugees")
async def refugees(request: Request):
    return await _layer_response(request, "refugees")


@router.get("/piracy")
async def piracy(request: Request):
    return await _layer_response(request, "piracy")


@router.get("/airspace")
async def airspace(request: Request):
    return await _layer_response(request, "airspace")


@router.get("/sanctions")
async def sanctions(request: Request):
    return await _layer_response(request, "sanctions")


@router.get("/cyber")
async def cyber(request: Request):
    return await _layer_response(request, "cyber")


@router.get("/military_bases")
async def military_bases(request: Request):
    return await _layer_response(request, "military_bases")


@router.get("/airports")
async def airports(request: Request):
    return await _layer_response(request, "airports")


@router.get("/notams")
async def notams(request: Request):
    return await _layer_response(request, "notams")


@router.get("/submarines")
async def submarines(request: Request):
    return await _layer_response(request, "submarines")


@router.get("/carriers")
async def carriers(request: Request):
    return await _layer_response(request, "carriers")


@router.get("/news")
async def news(request: Request):
    return await _layer_response(request, "news")


@router.get("/threat_intel")
async def threat_intel(request: Request):
    return await _layer_response(request, "threat_intel")


@router.get("/signals")
async def signals(request: Request):
    return await _layer_response(request, "signals")


# Strike-related keywords for mining Reddit OSINT posts
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

# Sub-event type inference from keywords
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

    # Mine Reddit OSINT
    for layer_name, source_label in [("reddit_osint", "Reddit"), ("telegram_osint", "Telegram")]:
        try:
            slot = cache.slot(layer_name)
        except KeyError:
            continue
        if not slot or not slot.entry.data:
            continue
        items = slot.entry.data
        if not isinstance(items, list):
            continue

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

            # Severity from engagement (Reddit has score/comments, Telegram has severity)
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
    """Missile/strike data enhanced with Reddit OSINT cross-reference.

    Merges the base missile_tests layer with geolocated Reddit posts
    mentioning strikes, missiles, bombings, airstrikes, and drone attacks.
    """
    cache = _cache(request)
    fns = _fetcher_fns(request)

    # Get base missile data
    base_data = await cache.get("missile_tests", fns["missile_tests"])

    # Cross-reference Reddit OSINT for additional strike reports
    reddit_strikes = _extract_osint_strikes(cache)

    if reddit_strikes:
        # Deduplicate: skip Reddit posts too close to existing missile events
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


@router.get("/telegram_osint")
async def telegram_osint(request: Request):
    return await _layer_response(request, "telegram_osint")


@router.get("/rocket_alerts")
async def rocket_alerts(request: Request):
    return await _layer_response(request, "rocket_alerts")


@router.get("/geo_confirmed")
async def geo_confirmed(request: Request):
    return await _layer_response(request, "geo_confirmed")


@router.get("/undersea_cables")
async def undersea_cables(request: Request):
    return await _layer_response(request, "undersea_cables")


@router.get("/live_streams")
async def live_streams(request: Request):
    return await _layer_response(request, "live_streams")


@router.get("/reddit_osint")
async def reddit_osint(request: Request):
    return await _layer_response(request, "reddit_osint")


@router.get("/equipment_losses")
async def equipment_losses(request: Request):
    return await _layer_response(request, "equipment_losses")


@router.get("/internet_outages")
async def internet_outages(request: Request):
    return await _layer_response(request, "internet_outages")


@router.get("/gps_jamming")
async def gps_jamming(request: Request):
    return await _layer_response(request, "gps_jamming")


@router.get("/natural_events")
async def natural_events(request: Request):
    return await _layer_response(request, "natural_events")


# ---------------------------------------------------------------------------
# 4D Timeline — Historical data snapshots
# ---------------------------------------------------------------------------

@router.get("/history/{layer}")
async def history(layer: str, request: Request, hours: float = 24.0):
    """Return timestamped snapshots for a layer within a time window."""
    cache = _cache(request)
    if layer not in cache._slots:
        return JSONResponse({"error": f"Unknown layer: {layer}"}, status_code=404)
    snapshots = cache.get_history(layer, hours=hours)
    return {"layer": layer, "hours": hours, "snapshots": snapshots}


@router.get("/history_summary")
async def history_summary(request: Request):
    """Return available history time ranges per layer."""
    cache = _cache(request)
    return cache.history_summary()


# ---------------------------------------------------------------------------
# Correlation Analysis — Cross-reference all OSINT layers
# ---------------------------------------------------------------------------

@router.get("/correlate")
async def correlate(request: Request):
    """Cross-reference all OSINT layers for intelligence correlation.

    Finds:
    - Conflicts near military bases (within 200km)
    - Missile strikes near critical infrastructure
    - Cyber threats targeting conflict zone countries
    - OSINT reports corroborating conflict events
    - Satellite passes over active conflict zones
    """
    import math
    cache = _cache(request)

    def _get_items(layer_name: str) -> list:
        try:
            slot = cache.slot(layer_name)
        except KeyError:
            return []
        if not slot or not slot.entry.data:
            return []
        data = slot.entry.data
        return data if isinstance(data, list) else []

    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Approximate distance in km between two points."""
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

    # Gather all layer data
    conflicts = _get_items("conflicts")
    missiles = _get_items("missile_tests")
    mil_bases = _get_items("military_bases")
    threat_intel = _get_items("threat_intel")
    telegram = _get_items("telegram_osint")
    reddit = _get_items("reddit_osint")
    carriers = _get_items("carriers")
    cyber = _get_items("cyber")

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

    # 4. OSINT corroboration (telegram + reddit mentioning same locations as conflicts)
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

    # Summary stats
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

    # Gather context from cached data
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

    # Satellite correlation
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

    # If LLM is configured, enhance with AI predictions
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


# ---------------------------------------------------------------------------
# YouTube Video Search (via GDELT DOC API proxy)
# ---------------------------------------------------------------------------

@router.get("/youtube_search")
async def youtube_search(request: Request, q: str = ""):
    """Dynamic video search — crawls cached OSINT data for video URLs.

    Zero hardcoded channels. Acts like a worm:
    1. Mine video URLs from cached Reddit OSINT (posts link to YouTube, v.redd.it, etc.)
    2. Mine video URLs from cached Telegram OSINT article links
    3. Crawl GDELT DOC API dynamically for YouTube links matching the query
    4. Scan cached news/conflicts for related article URLs
    5. Try Piped/Invidious API as final fallback search
    """
    import re as _re

    if not q.strip():
        return JSONResponse(content={"videos": [], "articles": []})

    client = _client(request)
    cache = _cache(request)
    videos: list = []
    articles: list = []
    seen_ids: set = set()
    seen_urls: set = set()
    query_lower = q.lower()
    q_words = [w for w in query_lower.split() if len(w) > 2]

    def _relevance_score(title: str) -> int:
        """Score how relevant a title is to the query."""
        t = title.lower()
        return sum(1 for w in q_words if w in t)

    def _try_extract_video(url: str, title: str, source: str, date: str = "") -> bool:
        """Try to extract a video from a URL. Returns True if video was added."""
        if not url:
            return False
        video_id = _extract_youtube_id(url)
        if video_id and video_id not in seen_ids:
            seen_ids.add(video_id)
            videos.append({
                "title": title[:200],
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "source": source,
                "date": date,
                "relevance": _relevance_score(title),
            })
            return True
        # Also capture Reddit video, Twitter video, etc.
        if any(d in url for d in ["v.redd.it", "streamable.com", "clips.twitch.tv"]):
            if url not in seen_urls:
                seen_urls.add(url)
                videos.append({
                    "title": title[:200],
                    "video_id": "",
                    "url": url,
                    "source": source,
                    "date": date,
                    "relevance": _relevance_score(title),
                })
                return True
        return False

    def _get_cached(layer_name: str) -> list:
        try:
            slot = cache.slot(layer_name)
        except KeyError:
            return []
        if not slot or not slot.entry.data:
            return []
        data = slot.entry.data
        return data if isinstance(data, list) else []

    # Source 1: Mine Reddit OSINT cache for video URLs
    # Reddit posts have url (permalink), media_url (linked content), has_media fields
    reddit_items = _get_cached("reddit_osint")
    for item in reddit_items:
        title = item.get("title", "")
        permalink = item.get("url", "")
        media_url = item.get("media_url", "")  # The actual linked content (YouTube, etc.)
        has_media = item.get("has_media", False)
        score = _relevance_score(title)

        # Only include if relevant to query
        if score >= 1 or (has_media and any(w in title.lower() for w in q_words)):
            # Try media_url first (this is the actual linked content — YouTube, video, etc.)
            if media_url:
                _try_extract_video(media_url, title, item.get("source", "Reddit"), item.get("date", ""))

            # Also try permalink (rarely has video but covers edge cases)
            _try_extract_video(permalink, title, item.get("source", "Reddit"), item.get("date", ""))

            # Track as article if not a video
            if permalink and permalink not in seen_urls and score >= 1:
                seen_urls.add(permalink)
                articles.append({
                    "title": title[:200],
                    "url": permalink,
                    "source": item.get("source", "Reddit"),
                    "date": item.get("date", ""),
                    "relevance": score,
                })

    # Source 2: Mine Telegram OSINT cache for article URLs with video content
    telegram_items = _get_cached("telegram_osint")
    for item in telegram_items:
        title = item.get("title", "")
        url = item.get("url", "")
        score = _relevance_score(title)
        if score >= 1:
            _try_extract_video(url, title, item.get("source", "OSINT Feed"), item.get("date", ""))
            # Also track as article if it's a news URL
            if url and "youtube" not in url and "youtu.be" not in url and url not in seen_urls:
                seen_urls.add(url)
                articles.append({
                    "title": title[:200],
                    "url": url,
                    "source": item.get("source", ""),
                    "date": item.get("date", ""),
                    "relevance": score,
                })

    # Source 3: Mine conflicts/news/missile_tests for related URLs
    for layer in ["conflicts", "news", "missile_tests", "piracy"]:
        layer_items = _get_cached(layer)
        for item in layer_items[:100]:
            title = item.get("title") or item.get("event_type") or item.get("name", "")
            url = item.get("url") or item.get("source_url", "")
            score = _relevance_score(title)
            if score >= 1 and url:
                _try_extract_video(url, title, item.get("source", layer), item.get("date", ""))

    # Source 4: GDELT DOC API — dynamically search for YouTube content
    try:
        resp = await client.get(
            "http://api.gdeltproject.org/api/v2/doc/doc",
            params={
                "query": f"{q} sourcelang:english",
                "mode": "ArtList",
                "maxrecords": "75",
                "format": "json",
                "TIMESPAN": "14D",
            },
            timeout=20.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            for art in (data.get("articles") or []):
                url = art.get("url", "")
                title = art.get("title", "")
                source = art.get("domain", "")
                date = art.get("seendate", "")

                _try_extract_video(url, title, source, date)

                # Track non-video articles too
                if url not in seen_urls and "youtube" not in url:
                    seen_urls.add(url)
                    articles.append({
                        "title": title[:200],
                        "url": url,
                        "source": source,
                        "date": date,
                        "relevance": _relevance_score(title),
                    })
    except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
        logger.debug("GDELT video search: %s", exc)

    # Source 5: GDELT TV API — find TV broadcast clips mentioning the query
    try:
        resp = await client.get(
            "http://api.gdeltproject.org/api/v2/tv/tv",
            params={
                "query": q,
                "mode": "clipgallery",
                "maxrecords": "20",
                "format": "json",
                "LAST24H": "YES",
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            for clip in (data.get("clips") or []):
                preview_url = clip.get("preview_url", "")
                show = clip.get("show", "")
                station = clip.get("station", "")
                snippet = clip.get("snippet", "")[:200]
                ia_url = clip.get("ia_show_id", "")  # Internet Archive URL

                if preview_url and preview_url not in seen_urls:
                    seen_urls.add(preview_url)
                    videos.append({
                        "title": f"{station}: {show}" if show else snippet,
                        "video_id": "",
                        "url": preview_url,
                        "source": station or "TV Broadcast",
                        "date": clip.get("date", ""),
                        "relevance": _relevance_score(snippet),
                    })
    except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
        logger.debug("GDELT TV search: %s", exc)

    # Source 6: Piped/Invidious API fallback (if we have fewer than 5 videos)
    if len(videos) < 5:
        piped_instances = [
            "https://pipedapi.kavin.rocks",
            "https://pipedapi.adminforge.de",
        ]
        for piped_url in piped_instances:
            if len(videos) >= 10:
                break
            try:
                resp = await client.get(
                    f"{piped_url}/search",
                    params={"q": q, "filter": "videos"},
                    timeout=8.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in (data.get("items") or []):
                        if item.get("type") != "stream":
                            continue
                        vid_url = item.get("url", "")
                        video_id = _extract_youtube_id(
                            f"https://youtube.com{vid_url}" if vid_url.startswith("/") else vid_url
                        )
                        if video_id and video_id not in seen_ids:
                            seen_ids.add(video_id)
                            videos.append({
                                "title": item.get("title", ""),
                                "video_id": video_id,
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "source": item.get("uploaderName", "YouTube"),
                                "date": "",
                                "relevance": _relevance_score(item.get("title", "")),
                            })
                        if len(videos) >= 10:
                            break
            except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
                logger.debug("Piped search %s: %s", piped_url, exc)

    # Sort all videos by relevance (best matches first)
    videos.sort(key=lambda v: v.get("relevance", 0), reverse=True)
    articles.sort(key=lambda a: a.get("relevance", 0), reverse=True)

    # Clean up relevance keys from output
    for v in videos:
        v.pop("relevance", None)
    for a in articles:
        a.pop("relevance", None)

    logger.info("Video search '%s': %d videos, %d articles (from cached OSINT + GDELT)",
                q, len(videos), len(articles))

    return JSONResponse(content={
        "videos": videos[:20],
        "articles": articles[:15],
        "query": q,
        "sources_scanned": {
            "reddit_osint": len(reddit_items),
            "telegram_osint": len(telegram_items),
            "gdelt": True,
            "gdelt_tv": True,
        },
    })


def _extract_youtube_id(url: str) -> str:
    """Extract YouTube video ID from URL."""
    import re
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


# ---------------------------------------------------------------------------
# Flight detail endpoint (per-icao24 with track)
# ---------------------------------------------------------------------------

async def _fetch_flight_detail(client: httpx.AsyncClient, icao24: str, intel: FlightIntelligence) -> dict:
    """Fetch detailed state + track for a single aircraft using adsb.lol (free, no rate limit)."""
    result: dict = {"icao24": icao24, "state": None, "track": []}

    # Primary: adsb.lol single-aircraft lookup
    try:
        resp = await client.get(
            f"https://api.airplanes.live/v2/hex/{icao24}",
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
        )
        resp.raise_for_status()
        data = resp.json()
        aircraft_list = data.get("ac") or []
        if aircraft_list:
            ac = aircraft_list[0]
            callsign = (ac.get("flight") or "").strip()
            squawk = ac.get("squawk")
            alt = ac.get("alt_baro")
            if alt == "ground":
                alt = 0
            result["state"] = {
                "icao24": icao24,
                "callsign": callsign,
                "origin_country": ac.get("r", ""),
                "longitude": ac.get("lon"),
                "latitude": ac.get("lat"),
                "baro_altitude": alt if isinstance(alt, (int, float)) else None,
                "on_ground": alt == 0 or alt == "ground",
                "velocity": ac.get("gs"),
                "heading": ac.get("track"),
                "vertical_rate": ac.get("baro_rate"),
                "geo_altitude": ac.get("alt_geom"),
                "squawk": squawk,
                "aircraft_type": ac.get("t", intel.estimate_aircraft_type(icao24)),
                "registration": ac.get("r", ""),
                "flight_route": intel.estimate_route(callsign),
                "is_military": intel.is_military(callsign, icao24) or intel.is_military_dbflags(ac.get("dbFlags", 0)),
                "squawk_alert": intel.detect_squawk_alert(squawk) if squawk else None,
            }
    except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
        logger.warning("adsb.lol detail fetch failed for %s: %s", icao24, exc)

    # Track/trace from airplanes.live (per-aircraft lookup)
    try:
        trace_resp = await client.get(
            f"https://api.airplanes.live/v2/hex/{icao24}",
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
        )
        trace_resp.raise_for_status()
        trace_data = trace_resp.json()
        trace_ac = (trace_data.get("ac") or [])
        # Build basic track from the aircraft's current position
        if trace_ac:
            ac = trace_ac[0]
            lat = ac.get("lat")
            lon = ac.get("lon")
            alt = ac.get("alt_baro")
            if isinstance(alt, str):
                alt = 0
            if lat is not None and lon is not None:
                result["track"] = [{
                    "latitude": lat,
                    "longitude": lon,
                    "altitude": alt if isinstance(alt, (int, float)) else 10000,
                }]
    except httpx.HTTPError as exc:
        logger.warning("airplanes.live trace fetch failed for %s: %s", icao24, exc)

    # Fallback: OpenSky track (may 429, but try)
    if not result["track"]:
        try:
            track_resp = await client.get(
                f"https://opensky-network.org/api/tracks/all?icao24={icao24}&time=0",
                timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            )
            track_resp.raise_for_status()
            track_data = track_resp.json()
            path = track_data.get("path") or []
            waypoints = []
            for wp in path:
                if len(wp) >= 4:
                    waypoints.append({
                        "latitude": wp[1], "longitude": wp[2],
                        "altitude": wp[3],
                    })
            result["track"] = waypoints
        except (httpx.HTTPError, httpx.TimeoutException):
            pass  # OpenSky often 429s, silently fall through

    return result


@router.get("/flight_detail/{icao24}")
async def flight_detail(icao24: str, request: Request):
    icao24 = icao24.lower().strip()
    if not icao24 or len(icao24) != 6:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid ICAO24 address. Must be a 6-character hex string."},
        )

    client = _client(request)
    intel = _intel(request)

    # Check cache freshness
    entry = _flight_detail_cache.get(icao24)
    if entry and entry.data is not None and (time.monotonic() - entry.fetched_at) < _FLIGHT_DETAIL_TTL:
        return JSONResponse(content=entry.data)

    if icao24 not in _flight_detail_locks:
        _flight_detail_locks[icao24] = asyncio.Lock()
    lock = _flight_detail_locks[icao24]

    async with lock:
        entry = _flight_detail_cache.get(icao24)
        if entry and entry.data is not None and (time.monotonic() - entry.fetched_at) < _FLIGHT_DETAIL_TTL:
            return JSONResponse(content=entry.data)

        try:
            data = await _fetch_flight_detail(client, icao24, intel)
            _flight_detail_cache[icao24] = CacheEntry(
                data=data, fetched_at=time.monotonic(),
                record_count=len(data.get("track", [])), error=None,
            )
            if len(_flight_detail_cache) > 500:
                oldest_keys = sorted(
                    _flight_detail_cache.keys(),
                    key=lambda k: _flight_detail_cache[k].fetched_at,
                )[:100]
                for k in oldest_keys:
                    _flight_detail_cache.pop(k, None)
                    _flight_detail_locks.pop(k, None)
            return JSONResponse(content=data)
        except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
            logger.error("Flight detail fetch failed for %s: %s", icao24, exc)
            if entry and entry.data is not None:
                return JSONResponse(content=entry.data)
            return JSONResponse(content={"icao24": icao24, "state": None, "track": [], "error": str(exc)})
