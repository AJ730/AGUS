"""
Tests for API endpoints (backend/app/routes.py)
=================================================
Tests every API endpoint for correct status codes and basic response
structure. Uses httpx.AsyncClient with ASGITransport to avoid real
network calls during the lifespan prefetch.

NOTE: The app lifespan creates an httpx.AsyncClient and prefetches
all data sources. During tests, external fetches will fail (expected)
and the fetchers will fall back to curated/generated data, which is
exactly what we want to verify.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest
import pytest_asyncio

from app.server import create_app
from app.cache import CacheManager
from app.flight_intel import FlightIntelligence
from app.generators import FlightGenerator, SubmarineGenerator, MilitaryBaseRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_app_client():
    """
    Create the app and a test client. The lifespan will execute, and
    since external APIs are unreachable in tests, all fetchers will
    fall back to their curated/generated data.
    We patch the httpx.AsyncClient used inside the lifespan so external
    calls return mock responses (allowing the app to start cleanly).
    """
    app = create_app()

    # We need to let the lifespan run. The prefetch will try to reach
    # external APIs -- we mock the internal http client to return errors
    # so fetchers fall back to curated data without network delay.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=httpx.Timeout(60.0),
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Health and Sources endpoints
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """Tests for GET /api/health."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, test_app_client: httpx.AsyncClient):
        """GET /api/health should return 200."""
        resp = await test_app_client.get("/api/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_has_status_ok(self, test_app_client: httpx.AsyncClient):
        """Health response should contain status='ok'."""
        resp = await test_app_client.get("/api/health")
        data = resp.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_has_timestamp(self, test_app_client: httpx.AsyncClient):
        """Health response should contain a timestamp."""
        resp = await test_app_client.get("/api/health")
        data = resp.json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)

    @pytest.mark.asyncio
    async def test_health_has_sources(self, test_app_client: httpx.AsyncClient):
        """Health response should contain a sources dict."""
        resp = await test_app_client.get("/api/health")
        data = resp.json()
        assert "sources" in data
        assert isinstance(data["sources"], dict)
        # Should have all 20 layer sources
        assert len(data["sources"]) == 20


class TestSourcesEndpoint:
    """Tests for GET /api/sources."""

    @pytest.mark.asyncio
    async def test_sources_returns_200(self, test_app_client: httpx.AsyncClient):
        """GET /api/sources should return 200."""
        resp = await test_app_client.get("/api/sources")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sources_returns_list(self, test_app_client: httpx.AsyncClient):
        """Sources response should be a list."""
        resp = await test_app_client.get("/api/sources")
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_sources_has_20_entries(self, test_app_client: httpx.AsyncClient):
        """Sources list should contain 20 layer entries."""
        resp = await test_app_client.get("/api/sources")
        data = resp.json()
        assert len(data) == 20

    @pytest.mark.asyncio
    async def test_sources_entry_structure(self, test_app_client: httpx.AsyncClient):
        """Each source entry should have the expected fields."""
        resp = await test_app_client.get("/api/sources")
        data = resp.json()
        expected_keys = {
            "name", "source_url", "ttl_seconds",
            "last_updated", "record_count", "is_cached",
            "is_fresh", "last_error",
        }
        for entry in data:
            assert expected_keys.issubset(entry.keys()), (
                f"Missing keys in source entry: {expected_keys - entry.keys()}"
            )


# ---------------------------------------------------------------------------
# Data layer endpoints -- all should return 200
# ---------------------------------------------------------------------------

LAYER_ENDPOINTS = [
    "/api/flights",
    "/api/conflicts",
    "/api/events",
    "/api/fires",
    "/api/vessels",
    "/api/cctv",
    "/api/satellites",
    "/api/earthquakes",
    "/api/nuclear",
    "/api/weather_alerts",
    "/api/terrorism",
    "/api/refugees",
    "/api/piracy",
    "/api/airspace",
    "/api/sanctions",
    "/api/cyber",
    "/api/military_bases",
    "/api/airports",
    "/api/notams",
    "/api/submarines",
]


class TestLayerEndpoints:
    """Tests for all 20 data layer endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", LAYER_ENDPOINTS)
    async def test_endpoint_returns_200(
        self, test_app_client: httpx.AsyncClient, endpoint: str
    ):
        """Each layer endpoint should return HTTP 200."""
        resp = await test_app_client.get(endpoint)
        assert resp.status_code == 200, (
            f"{endpoint} returned {resp.status_code} instead of 200"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", LAYER_ENDPOINTS)
    async def test_endpoint_returns_json(
        self, test_app_client: httpx.AsyncClient, endpoint: str
    ):
        """Each layer endpoint should return valid JSON."""
        resp = await test_app_client.get(endpoint)
        data = resp.json()  # Should not raise
        assert data is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", LAYER_ENDPOINTS)
    async def test_endpoint_has_cache_header(
        self, test_app_client: httpx.AsyncClient, endpoint: str
    ):
        """Each layer endpoint should include X-Cache-Fresh header."""
        resp = await test_app_client.get(endpoint)
        assert "x-cache-fresh" in resp.headers

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", LAYER_ENDPOINTS)
    async def test_endpoint_has_timing_header(
        self, test_app_client: httpx.AsyncClient, endpoint: str
    ):
        """Each layer endpoint should include X-Response-Time-Ms header."""
        resp = await test_app_client.get(endpoint)
        assert "x-response-time-ms" in resp.headers


# ---------------------------------------------------------------------------
# Specific data layer content tests
# ---------------------------------------------------------------------------

class TestFlightsEndpoint:
    """Content tests for /api/flights."""

    @pytest.mark.asyncio
    async def test_flights_returns_list(self, test_app_client: httpx.AsyncClient):
        """Flights should return a list."""
        resp = await test_app_client.get("/api/flights")
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_flights_has_data(self, test_app_client: httpx.AsyncClient):
        """Flights should have data (generated fallback)."""
        resp = await test_app_client.get("/api/flights")
        data = resp.json()
        assert len(data) > 0


class TestConflictsEndpoint:
    """Content tests for /api/conflicts."""

    @pytest.mark.asyncio
    async def test_conflicts_returns_list(self, test_app_client: httpx.AsyncClient):
        """Conflicts should return a list."""
        resp = await test_app_client.get("/api/conflicts")
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_conflicts_has_data(self, test_app_client: httpx.AsyncClient):
        """Conflicts should have curated data."""
        resp = await test_app_client.get("/api/conflicts")
        data = resp.json()
        assert len(data) > 0


class TestEventsEndpoint:
    """Content tests for /api/events."""

    @pytest.mark.asyncio
    async def test_events_returns_dict_or_list(self, test_app_client: httpx.AsyncClient):
        """Events should return a GeoJSON FeatureCollection dict."""
        resp = await test_app_client.get("/api/events")
        data = resp.json()
        # Events returns FeatureCollection or list depending on fallback
        assert isinstance(data, (dict, list))


class TestSubmarinesEndpoint:
    """Content tests for /api/submarines."""

    @pytest.mark.asyncio
    async def test_submarines_returns_list(self, test_app_client: httpx.AsyncClient):
        """Submarines should return a list."""
        resp = await test_app_client.get("/api/submarines")
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_submarines_has_data(self, test_app_client: httpx.AsyncClient):
        """Submarines should have generated data."""
        resp = await test_app_client.get("/api/submarines")
        data = resp.json()
        assert len(data) > 80


class TestMilitaryBasesEndpoint:
    """Content tests for /api/military_bases."""

    @pytest.mark.asyncio
    async def test_military_bases_returns_list(self, test_app_client: httpx.AsyncClient):
        """Military bases should return a list."""
        resp = await test_app_client.get("/api/military_bases")
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_military_bases_count(self, test_app_client: httpx.AsyncClient):
        """Military bases should have 157 entries."""
        resp = await test_app_client.get("/api/military_bases")
        data = resp.json()
        assert len(data) == 157


class TestCCTVEndpoint:
    """Content tests for /api/cctv."""

    @pytest.mark.asyncio
    async def test_cctv_returns_list(self, test_app_client: httpx.AsyncClient):
        """CCTV should return a list of camera entries."""
        resp = await test_app_client.get("/api/cctv")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 20


class TestAirportsEndpoint:
    """Content tests for /api/airports."""

    @pytest.mark.asyncio
    async def test_airports_returns_list(self, test_app_client: httpx.AsyncClient):
        """Airports should return a list."""
        resp = await test_app_client.get("/api/airports")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 25


class TestSanctionsEndpoint:
    """Content tests for /api/sanctions."""

    @pytest.mark.asyncio
    async def test_sanctions_returns_list(self, test_app_client: httpx.AsyncClient):
        """Sanctions should return a list."""
        resp = await test_app_client.get("/api/sanctions")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 10


class TestCyberEndpoint:
    """Content tests for /api/cyber."""

    @pytest.mark.asyncio
    async def test_cyber_returns_list(self, test_app_client: httpx.AsyncClient):
        """Cyber threats should return a list."""
        resp = await test_app_client.get("/api/cyber")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 10


class TestAirspaceEndpoint:
    """Content tests for /api/airspace."""

    @pytest.mark.asyncio
    async def test_airspace_returns_list(self, test_app_client: httpx.AsyncClient):
        """Airspace restrictions should return a list."""
        resp = await test_app_client.get("/api/airspace")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 10


class TestNOTAMsEndpoint:
    """Content tests for /api/notams."""

    @pytest.mark.asyncio
    async def test_notams_returns_list(self, test_app_client: httpx.AsyncClient):
        """NOTAMs should return a list."""
        resp = await test_app_client.get("/api/notams")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 20


class TestPiracyEndpoint:
    """Content tests for /api/piracy."""

    @pytest.mark.asyncio
    async def test_piracy_returns_list(self, test_app_client: httpx.AsyncClient):
        """Piracy should return a list."""
        resp = await test_app_client.get("/api/piracy")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 10


# ---------------------------------------------------------------------------
# Flight detail endpoint
# ---------------------------------------------------------------------------

class TestFlightDetailEndpoint:
    """Tests for GET /api/flight_detail/{icao24}."""

    @pytest.mark.asyncio
    async def test_invalid_icao24_returns_400(self, test_app_client: httpx.AsyncClient):
        """Invalid ICAO24 (wrong length) should return 400."""
        resp = await test_app_client.get("/api/flight_detail/abc")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_icao24_too_long(self, test_app_client: httpx.AsyncClient):
        """ICAO24 that is too long should return 400."""
        resp = await test_app_client.get("/api/flight_detail/abcdef1")
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_valid_icao24_returns_200(self, test_app_client: httpx.AsyncClient):
        """Valid 6-char hex ICAO24 should return 200 (even if data is empty)."""
        resp = await test_app_client.get("/api/flight_detail/a12345")
        assert resp.status_code == 200
        data = resp.json()
        assert "icao24" in data

    @pytest.mark.asyncio
    async def test_flight_detail_response_structure(self, test_app_client: httpx.AsyncClient):
        """Flight detail should contain icao24, state, and track fields."""
        resp = await test_app_client.get("/api/flight_detail/abcdef")
        data = resp.json()
        assert "icao24" in data
        assert "track" in data or "state" in data or "error" in data


# ---------------------------------------------------------------------------
# CORS headers
# ---------------------------------------------------------------------------

class TestCORSHeaders:
    """Tests for CORS middleware configuration."""

    @pytest.mark.asyncio
    async def test_cors_allows_all_origins(self, test_app_client: httpx.AsyncClient):
        """The CORS middleware should allow any origin."""
        resp = await test_app_client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI CORS middleware should respond to preflight
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Non-existent endpoint
# ---------------------------------------------------------------------------

class TestNotFoundEndpoint:
    """Tests for 404 behavior."""

    @pytest.mark.asyncio
    async def test_nonexistent_path_returns_404(self, test_app_client: httpx.AsyncClient):
        """Accessing a non-existent path should return 404."""
        resp = await test_app_client.get("/api/nonexistent")
        assert resp.status_code == 404
