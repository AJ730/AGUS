"""Agus OSINT Backend -- API Routes (package).

Aggregates all sub-routers under the ``/api`` prefix so the import in
``server.py`` stays unchanged::

    from .routes import router
"""

from __future__ import annotations

from fastapi import APIRouter

from .health import router as health_router
from .layers import router as layers_router
from .flights import router as flights_router
from .intelligence import router as intelligence_router
from .search import router as search_router

router = APIRouter(prefix="/api")
router.include_router(health_router)
router.include_router(layers_router)
router.include_router(flights_router)
router.include_router(intelligence_router)
router.include_router(search_router)
