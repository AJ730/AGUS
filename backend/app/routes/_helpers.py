"""Shared helpers for route modules."""

from __future__ import annotations

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from ..cache import CacheManager
from ..flight_intel import FlightIntelligence


def _cache(request: Request) -> CacheManager:
    """Return the CacheManager from app state."""
    return request.app.state.cache_manager


def _client(request: Request) -> httpx.AsyncClient:
    """Return the shared HTTP client from app state."""
    return request.app.state.http_client


def _fetcher_fns(request: Request) -> dict:
    """Return the fetcher-function map from app state."""
    return request.app.state.fetcher_fns


def _intel(request: Request) -> FlightIntelligence:
    """Return the FlightIntelligence instance from app state."""
    return request.app.state.flight_intel


async def layer_response(request: Request, name: str) -> JSONResponse:
    """Generic layer endpoint: return cached data for *name*."""
    cache = _cache(request)
    fns = _fetcher_fns(request)
    data = await cache.get(name, fns[name])
    return JSONResponse(
        content=data,
        headers={"X-Cache-Fresh": str(cache.slot(name).is_fresh).lower()},
    )


def get_cached_items(cache: CacheManager, layer_name: str) -> list:
    """Safely read cached list data from a layer slot."""
    try:
        slot = cache.slot(layer_name)
    except KeyError:
        return []
    if not slot or not slot.entry.data:
        return []
    data = slot.entry.data
    return data if isinstance(data, list) else []
