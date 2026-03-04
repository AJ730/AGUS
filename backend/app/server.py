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
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .cache import CacheManager
from .config import CONNECTION_LIMITS, LAYER_CONFIG, REQUEST_TIMEOUT
from .flight_intel import FlightIntelligence
from .registry import build_registry
from .routes import router
from .scheduler import build_scheduler

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
    registry = build_registry(intel)

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
    scheduler = build_scheduler(cache, fetcher_fns)

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
        async def _background_prefetch():
            logger.info("Pre-fetching all OSINT sources (background) ...")
            await cache.prefetch_all(fetcher_fns)
            logger.info("Pre-fetch complete.")

        prefetch_task = asyncio.create_task(_background_prefetch())

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
