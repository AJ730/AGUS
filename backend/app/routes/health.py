"""Health, sources, and history endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ._helpers import _cache

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    """Overall system health with per-source status."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": _cache(request).status(),
    }


@router.get("/sources")
async def sources(request: Request):
    """Flat list of all registered data sources."""
    return _cache(request).sources_list()


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
    return _cache(request).history_summary()
