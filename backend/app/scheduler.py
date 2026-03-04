"""Scheduler builder — periodic refresh jobs for cached OSINT data."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .cache import CacheManager

logger = logging.getLogger("agus")

# Type alias for the fetcher-function map
FetcherFnMap = Dict[str, Callable]


async def _refresh_fast(cache: CacheManager, fns: FetcherFnMap) -> None:
    """High-frequency sources (~45 s): flights, vessels, satellites, radiosondes."""
    await asyncio.gather(
        cache.get("flights", fns["flights"]),
        cache.get("vessels", fns["vessels"]),
        cache.get("satellites", fns["satellites"]),
        cache.get("radiosondes", fns["radiosondes"]),
        cache.get("n2yo_satellites", fns["n2yo_satellites"]),
        return_exceptions=True,
    )


async def _refresh_fast_intel(cache: CacheManager, fns: FetcherFnMap) -> None:
    """Fast intel sources (~60 s): alerts, OSINT feeds, space weather."""
    await asyncio.gather(
        cache.get("rocket_alerts", fns["rocket_alerts"]),
        cache.get("telegram_osint", fns["telegram_osint"]),
        cache.get("reddit_osint", fns["reddit_osint"]),
        cache.get("internet_outages", fns["internet_outages"]),
        cache.get("mastodon_osint", fns["mastodon_osint"]),
        cache.get("space_weather", fns["space_weather"]),
        cache.get("space_launches", fns["space_launches"]),
        return_exceptions=True,
    )


async def _refresh_medium(cache: CacheManager, fns: FetcherFnMap) -> None:
    """Medium-frequency sources (~5 min): fires, quakes, nuclear, weather."""
    await asyncio.gather(
        cache.get("fires", fns["fires"]),
        cache.get("earthquakes", fns["earthquakes"]),
        cache.get("nuclear", fns["nuclear"]),
        cache.get("weather_alerts", fns["weather_alerts"]),
        return_exceptions=True,
    )
    await asyncio.sleep(2.0)
    await cache.get("events", fns["events"])


async def _refresh_slow(cache: CacheManager, fns: FetcherFnMap) -> None:
    """Slow sources (~30 min): stagger GDELT-dependent layers."""
    await cache.get("cyber", fns["cyber"])
    await cache.get("threat_intel", fns["threat_intel"])
    for name in ["conflicts", "cctv", "terrorism", "piracy", "news", "missile_tests", "protests", "deforestation"]:
        await cache.get(name, fns[name])
        await asyncio.sleep(3.0)


async def _refresh_very_slow(cache: CacheManager, fns: FetcherFnMap) -> None:
    """Very slow sources (~6 h): non-GDELT concurrent, then GDELT staggered."""
    await asyncio.gather(
        cache.get("refugees", fns["refugees"]),
        cache.get("sanctions", fns["sanctions"]),
        cache.get("airports", fns["airports"]),
        cache.get("submarines", fns["submarines"]),
        cache.get("carriers", fns["carriers"]),
        cache.get("military_bases", fns["military_bases"]),
        cache.get("signals", fns["signals"]),
        cache.get("undersea_cables", fns["undersea_cables"]),
        cache.get("geo_confirmed", fns["geo_confirmed"]),
        cache.get("live_streams", fns["live_streams"]),
        cache.get("equipment_losses", fns["equipment_losses"]),
        cache.get("gps_jamming", fns["gps_jamming"]),
        cache.get("volcanoes", fns["volcanoes"]),
        cache.get("asteroids", fns["asteroids"]),
        cache.get("disease_outbreaks", fns["disease_outbreaks"]),
        cache.get("critical_infrastructure", fns["critical_infrastructure"]),
        return_exceptions=True,
    )
    await asyncio.sleep(2.0)
    await cache.get("airspace", fns["airspace"])
    await asyncio.sleep(3.0)
    await cache.get("notams", fns["notams"])


def build_scheduler(cache: CacheManager, fns: FetcherFnMap) -> AsyncIOScheduler:
    """Create and configure the APScheduler with all refresh jobs.

    Args:
        cache: Shared CacheManager.
        fns: Map of layer name → async fetch callable.

    Returns:
        Configured (but not yet started) AsyncIOScheduler.
    """
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: _refresh_fast(cache, fns), "interval", seconds=45, id="fast")
    scheduler.add_job(lambda: _refresh_fast_intel(cache, fns), "interval", seconds=60, id="fast_intel")
    scheduler.add_job(lambda: _refresh_medium(cache, fns), "interval", seconds=300, id="medium")
    scheduler.add_job(lambda: _refresh_slow(cache, fns), "interval", seconds=1800, id="slow")
    scheduler.add_job(lambda: _refresh_very_slow(cache, fns), "interval", seconds=21600, id="very_slow")
    return scheduler
