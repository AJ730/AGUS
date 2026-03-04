"""
Agus OSINT Backend -- Application Factory
==============================================
Creates and configures the FastAPI application with all dependencies
wired together.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .cache import CacheManager
from .config import CONNECTION_LIMITS, LAYER_CONFIG, REQUEST_TIMEOUT
from .fetchers import (
    AirportFetcher,
    AirspaceFetcher,
    CCTVFetcher,
    ConflictFetcher,
    CyberFetcher,
    EarthquakeFetcher,
    EventFetcher,
    FetcherRegistry,
    FireFetcher,
    FlightFetcher,
    MilitaryBaseFetcher,
    MissileTestFetcher,
    NOTAMFetcher,
    NuclearFetcher,
    PiracyFetcher,
    RefugeeFetcher,
    RocketAlertFetcher,
    GeoConfirmedFetcher,
    UnderseaCableFetcher,
    LiveStreamFetcher,
    SanctionsFetcher,
    SatelliteFetcher,
    SubmarineFetcher,
    CarrierFetcher,
    NewsFetcher,
    TelegramOSINTFetcher,
    TerrorismFetcher,
    ThreatIntelFetcher,
    SignalsFetcher,
    VesselFetcher,
    WeatherAlertFetcher,
    RedditOSINTFetcher,
    EquipmentLossFetcher,
    InternetOutageFetcher,
    GPSJammingFetcher,
    EONETFetcher,
)
from .flight_intel import FlightIntelligence
from .routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("agus")


def create_app() -> FastAPI:
    """Build and return the fully-configured FastAPI application."""

    # --- Domain objects ---
    cache = CacheManager()
    intel = FlightIntelligence()

    # --- Register all cache slots from config ---
    for name, cfg in LAYER_CONFIG.items():
        cache.register(name, cfg["ttl"], cfg["source_url"])

    # --- Build fetcher registry ---
    registry = FetcherRegistry()
    registry.register("flights", FlightFetcher(intel))
    registry.register("conflicts", ConflictFetcher())
    registry.register("events", EventFetcher())
    registry.register("fires", FireFetcher())
    registry.register("vessels", VesselFetcher())
    registry.register("cctv", CCTVFetcher())
    registry.register("satellites", SatelliteFetcher())
    registry.register("earthquakes", EarthquakeFetcher())
    registry.register("nuclear", NuclearFetcher())
    registry.register("weather_alerts", WeatherAlertFetcher())
    registry.register("terrorism", TerrorismFetcher())
    registry.register("refugees", RefugeeFetcher())
    registry.register("piracy", PiracyFetcher())
    registry.register("airspace", AirspaceFetcher())
    registry.register("sanctions", SanctionsFetcher())
    registry.register("cyber", CyberFetcher())
    registry.register("military_bases", MilitaryBaseFetcher())
    registry.register("airports", AirportFetcher())
    registry.register("notams", NOTAMFetcher())
    registry.register("submarines", SubmarineFetcher())
    registry.register("carriers", CarrierFetcher())
    registry.register("news", NewsFetcher())
    registry.register("threat_intel", ThreatIntelFetcher())
    registry.register("signals", SignalsFetcher())
    registry.register("missile_tests", MissileTestFetcher())
    registry.register("telegram_osint", TelegramOSINTFetcher())
    registry.register("rocket_alerts", RocketAlertFetcher())
    registry.register("geo_confirmed", GeoConfirmedFetcher())
    registry.register("undersea_cables", UnderseaCableFetcher())
    registry.register("live_streams", LiveStreamFetcher())
    registry.register("reddit_osint", RedditOSINTFetcher())
    registry.register("equipment_losses", EquipmentLossFetcher())
    registry.register("internet_outages", InternetOutageFetcher())
    registry.register("gps_jamming", GPSJammingFetcher())
    registry.register("natural_events", EONETFetcher())

    # --- HTTP client ref (created in lifespan) ---
    http_client_ref: dict = {"client": None}

    # --- Build fetcher function map (cache.get expects async callables) ---
    def _make_fetcher_fn(fetcher_name: str):
        """Return an async closure that fetches using the shared HTTP client."""
        fetcher = registry.get(fetcher_name)

        async def _fn():
            return await fetcher.fetch(http_client_ref["client"])

        return _fn

    fetcher_fns = {name: _make_fetcher_fn(name) for name in registry.names()}

    # --- Scheduler ---
    scheduler = AsyncIOScheduler()

    async def _refresh_fast():
        await asyncio.gather(
            cache.get("flights", fetcher_fns["flights"]),
            cache.get("vessels", fetcher_fns["vessels"]),
            cache.get("satellites", fetcher_fns["satellites"]),
            return_exceptions=True,
        )

    async def _refresh_medium():
        """events uses GDELT, so fetch it separately with delay."""
        await asyncio.gather(
            cache.get("fires", fetcher_fns["fires"]),
            cache.get("earthquakes", fetcher_fns["earthquakes"]),
            cache.get("nuclear", fetcher_fns["nuclear"]),
            cache.get("weather_alerts", fetcher_fns["weather_alerts"]),
            return_exceptions=True,
        )
        await asyncio.sleep(2.0)
        await cache.get("events", fetcher_fns["events"])

    async def _refresh_fast_intel():
        """Refresh high-frequency intel sources."""
        await asyncio.gather(
            cache.get("rocket_alerts", fetcher_fns["rocket_alerts"]),
            cache.get("telegram_osint", fetcher_fns["telegram_osint"]),
            cache.get("reddit_osint", fetcher_fns["reddit_osint"]),
            cache.get("internet_outages", fetcher_fns["internet_outages"]),
            return_exceptions=True,
        )

    async def _refresh_slow():
        """Stagger GDELT-dependent sources to avoid rate limiting."""
        await cache.get("cyber", fetcher_fns["cyber"])
        await cache.get("threat_intel", fetcher_fns["threat_intel"])
        for name in ["conflicts", "cctv", "terrorism", "piracy", "news", "missile_tests"]:
            await cache.get(name, fetcher_fns[name])
            await asyncio.sleep(3.0)

    async def _refresh_very_slow():
        """Non-GDELT sources concurrent, then GDELT sources staggered."""
        await asyncio.gather(
            cache.get("refugees", fetcher_fns["refugees"]),
            cache.get("sanctions", fetcher_fns["sanctions"]),
            cache.get("airports", fetcher_fns["airports"]),
            cache.get("submarines", fetcher_fns["submarines"]),
            cache.get("carriers", fetcher_fns["carriers"]),
            cache.get("military_bases", fetcher_fns["military_bases"]),
            cache.get("signals", fetcher_fns["signals"]),
            cache.get("undersea_cables", fetcher_fns["undersea_cables"]),
            cache.get("geo_confirmed", fetcher_fns["geo_confirmed"]),
            cache.get("live_streams", fetcher_fns["live_streams"]),
            cache.get("equipment_losses", fetcher_fns["equipment_losses"]),
            cache.get("gps_jamming", fetcher_fns["gps_jamming"]),
            return_exceptions=True,
        )
        await asyncio.sleep(2.0)
        await cache.get("airspace", fetcher_fns["airspace"])
        await asyncio.sleep(3.0)
        await cache.get("notams", fetcher_fns["notams"])

    # --- Lifespan ---
    async def _lifespan(app: FastAPI):
        logger.info("Starting Agus OSINT backend ...")
        http_client_ref["client"] = httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            limits=CONNECTION_LIMITS,
            follow_redirects=True,
            http2=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
            },
        )

        # Expose shared state for routes
        app.state.cache_manager = cache
        app.state.http_client = http_client_ref["client"]
        app.state.fetcher_fns = fetcher_fns
        app.state.flight_intel = intel

        # Pre-fetch in background so the server starts accepting connections immediately
        # (Fly.io health checks need a response within 60s)
        async def _background_prefetch():
            logger.info("Pre-fetching all OSINT sources (background) ...")
            await cache.prefetch_all(fetcher_fns)
            logger.info("Pre-fetch complete.")

        prefetch_task = asyncio.create_task(_background_prefetch())

        # Schedule periodic refreshes
        scheduler.add_job(_refresh_fast, "interval", seconds=45, id="fast")
        scheduler.add_job(_refresh_fast_intel, "interval", seconds=60, id="fast_intel")
        scheduler.add_job(_refresh_medium, "interval", seconds=300, id="medium")
        scheduler.add_job(_refresh_slow, "interval", seconds=1800, id="slow")
        scheduler.add_job(_refresh_very_slow, "interval", seconds=21600, id="very_slow")
        scheduler.start()
        logger.info("Server ready — background prefetch in progress.")

        yield  # app is running

        logger.info("Shutting down ...")
        if not prefetch_task.done():
            prefetch_task.cancel()
        scheduler.shutdown(wait=False)
        await http_client_ref["client"].aclose()
        http_client_ref["client"] = None
        logger.info("Shutdown complete.")

    # --- Build app ---
    app = FastAPI(
        title="Agus OSINT Aggregator",
        description="Live conflict-monitoring data aggregation from free OSINT sources.",
        version="2.0.0",
        lifespan=_lifespan,
    )

    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Timing middleware
    @app.middleware("http")
    async def add_timing_header(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response

    app.include_router(router)

    return app
