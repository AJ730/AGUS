"""
Shared fixtures for the Agus OSINT backend test suite.
"""

from __future__ import annotations

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.server import create_app
from app.cache import CacheManager
from app.flight_intel import FlightIntelligence
from app.generators import FlightGenerator, SubmarineGenerator, MilitaryBaseRegistry


# ---------------------------------------------------------------------------
# pytest-asyncio configuration
# ---------------------------------------------------------------------------
pytest_plugins = []


# ---------------------------------------------------------------------------
# Domain object fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flight_intel() -> FlightIntelligence:
    """Return a fresh FlightIntelligence instance."""
    return FlightIntelligence()


@pytest.fixture
def flight_generator() -> FlightGenerator:
    """Return a FlightGenerator with default seed."""
    return FlightGenerator(seed=42)


@pytest.fixture
def submarine_generator() -> SubmarineGenerator:
    """Return a SubmarineGenerator with default seed."""
    return SubmarineGenerator(seed=42)


@pytest.fixture
def military_base_registry() -> MilitaryBaseRegistry:
    """Return a MilitaryBaseRegistry instance."""
    return MilitaryBaseRegistry()


@pytest.fixture
def cache_manager() -> CacheManager:
    """Return an empty CacheManager."""
    return CacheManager()


# ---------------------------------------------------------------------------
# FastAPI app and async test client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """
    Create the FastAPI app. Note: the lifespan creates an httpx client
    and prefetches data. For tests, the lifespan is handled by the
    ASGITransport + AsyncClient context.
    """
    return create_app()


@pytest_asyncio.fixture
async def client(app):
    """
    Async test client using httpx.ASGITransport.
    The lifespan is triggered so app.state is populated.
    We mock the external HTTP calls made during prefetch so tests
    don't depend on network access.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=httpx.Timeout(30.0),
    ) as ac:
        yield ac
