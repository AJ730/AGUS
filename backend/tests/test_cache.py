"""
Tests for app.cache.CacheManager, CacheSlot, and CacheEntry
==============================================================
Covers registration, TTL-based freshness, double-checked locking,
error fallback behaviour, status/sources reporting.
"""

from __future__ import annotations

import asyncio
import time

import pytest
import pytest_asyncio

from app.cache import CacheEntry, CacheManager, CacheSlot


# ===================================================================
#  CacheEntry
# ===================================================================

class TestCacheEntry:
    """Tests for the CacheEntry dataclass."""

    def test_default_values(self):
        """Default CacheEntry should have None data, 0.0 fetched_at, etc."""
        entry = CacheEntry()
        assert entry.data is None
        assert entry.fetched_at == 0.0
        assert entry.record_count == 0
        assert entry.error is None

    def test_custom_values(self):
        """CacheEntry should accept custom values."""
        entry = CacheEntry(
            data=[1, 2, 3],
            fetched_at=100.0,
            record_count=3,
            error="test error",
        )
        assert entry.data == [1, 2, 3]
        assert entry.fetched_at == 100.0
        assert entry.record_count == 3
        assert entry.error == "test error"


# ===================================================================
#  CacheSlot
# ===================================================================

class TestCacheSlot:
    """Tests for the CacheSlot dataclass."""

    def test_default_slot_not_fresh(self):
        """A newly created CacheSlot (fetched_at=0) should not be fresh."""
        slot = CacheSlot(name="test", ttl_seconds=60.0, source_url="http://example.com")
        assert slot.is_fresh is False

    def test_slot_with_recent_fetch_is_fresh(self):
        """A slot with a recent fetch should be considered fresh."""
        slot = CacheSlot(name="test", ttl_seconds=60.0, source_url="http://example.com")
        slot.entry = CacheEntry(data=[1], fetched_at=time.monotonic(), record_count=1)
        assert slot.is_fresh is True

    def test_slot_with_old_fetch_not_fresh(self):
        """A slot whose fetch is older than TTL should not be fresh."""
        slot = CacheSlot(name="test", ttl_seconds=1.0, source_url="http://example.com")
        slot.entry = CacheEntry(
            data=[1], fetched_at=time.monotonic() - 10.0, record_count=1,
        )
        assert slot.is_fresh is False

    def test_last_updated_iso_none_when_never_fetched(self):
        """last_updated_iso should be None if never fetched."""
        slot = CacheSlot(name="test", ttl_seconds=60.0, source_url="http://example.com")
        assert slot.last_updated_iso is None

    def test_last_updated_iso_returns_string_when_fetched(self):
        """last_updated_iso should return an ISO string after fetch."""
        slot = CacheSlot(name="test", ttl_seconds=60.0, source_url="http://example.com")
        slot.entry = CacheEntry(data=[], fetched_at=time.monotonic(), record_count=0)
        iso_str = slot.last_updated_iso
        assert iso_str is not None
        assert isinstance(iso_str, str)
        # Should be a valid ISO format (contains 'T' and timezone info)
        assert "T" in iso_str


# ===================================================================
#  CacheManager -- register, get, status, sources
# ===================================================================

class TestCacheManager:
    """Tests for CacheManager."""

    @pytest.fixture
    def manager(self) -> CacheManager:
        cm = CacheManager()
        cm.register("test_slot", ttl=60.0, source_url="http://example.com/test")
        cm.register("events", ttl=300.0, source_url="http://example.com/events")
        return cm

    def test_register_creates_slot(self, manager: CacheManager):
        """Registering a slot should make it accessible."""
        slot = manager.slot("test_slot")
        assert slot.name == "test_slot"
        assert slot.ttl_seconds == 60.0
        assert slot.source_url == "http://example.com/test"

    def test_slot_raises_on_unknown(self, manager: CacheManager):
        """Accessing an unregistered slot should raise KeyError."""
        with pytest.raises(KeyError):
            manager.slot("nonexistent")

    @pytest.mark.asyncio
    async def test_get_fetches_data_when_stale(self, manager: CacheManager):
        """get() should call the fetcher when the cache is stale/empty."""
        call_count = 0

        async def fetcher():
            nonlocal call_count
            call_count += 1
            return [{"id": 1}, {"id": 2}]

        data = await manager.get("test_slot", fetcher)
        assert call_count == 1
        assert data == [{"id": 1}, {"id": 2}]

    @pytest.mark.asyncio
    async def test_get_returns_cached_when_fresh(self, manager: CacheManager):
        """get() should NOT call the fetcher when the cache is fresh."""
        call_count = 0

        async def fetcher():
            nonlocal call_count
            call_count += 1
            return [{"id": 1}]

        # First call populates the cache
        await manager.get("test_slot", fetcher)
        assert call_count == 1

        # Second call should use cached data
        data = await manager.get("test_slot", fetcher)
        assert call_count == 1  # Not called again
        assert data == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_get_counts_list_records(self, manager: CacheManager):
        """Record count should match list length for list data."""
        async def fetcher():
            return [1, 2, 3, 4, 5]

        await manager.get("test_slot", fetcher)
        slot = manager.slot("test_slot")
        assert slot.entry.record_count == 5

    @pytest.mark.asyncio
    async def test_get_counts_feature_collection_records(self, manager: CacheManager):
        """Record count should match features count for GeoJSON FeatureCollection."""
        async def fetcher():
            return {
                "type": "FeatureCollection",
                "features": [{"type": "Feature"}, {"type": "Feature"}],
            }

        await manager.get("events", fetcher)
        slot = manager.slot("events")
        assert slot.entry.record_count == 2

    @pytest.mark.asyncio
    async def test_get_error_returns_stale_data(self, manager: CacheManager):
        """On fetcher error, get() should return stale data if available."""
        call_count = 0

        async def good_fetcher():
            nonlocal call_count
            call_count += 1
            return [{"id": "ok"}]

        async def bad_fetcher():
            raise RuntimeError("Network error")

        # Populate the cache
        await manager.get("test_slot", good_fetcher)

        # Force cache to be stale by setting fetched_at far in the past
        manager.slot("test_slot").entry.fetched_at = 0.0

        # Now the fetcher fails, but we should still get the old data
        data = await manager.get("test_slot", bad_fetcher)
        assert data == [{"id": "ok"}]

    @pytest.mark.asyncio
    async def test_get_error_with_no_data_returns_empty_list(self, manager: CacheManager):
        """On fetcher error with no cached data, get() returns empty list."""
        async def bad_fetcher():
            raise RuntimeError("Network error")

        data = await manager.get("test_slot", bad_fetcher)
        assert data == []

    @pytest.mark.asyncio
    async def test_get_error_events_returns_feature_collection(self, manager: CacheManager):
        """On fetcher error for 'events' with no data, returns empty FeatureCollection."""
        async def bad_fetcher():
            raise RuntimeError("Network error")

        data = await manager.get("events", bad_fetcher)
        assert isinstance(data, dict)
        assert data["type"] == "FeatureCollection"
        assert data["features"] == []

    @pytest.mark.asyncio
    async def test_get_records_error_string(self, manager: CacheManager):
        """When a fetch fails, the error should be recorded on the slot."""
        async def bad_fetcher():
            raise ValueError("Something broke")

        await manager.get("test_slot", bad_fetcher)
        slot = manager.slot("test_slot")
        assert slot.entry.error is not None
        assert "Something broke" in slot.entry.error

    def test_status_returns_dict(self, manager: CacheManager):
        """status() should return a dict with slot names as keys."""
        status = manager.status()
        assert isinstance(status, dict)
        assert "test_slot" in status
        assert "events" in status

    def test_status_contains_is_fresh_and_record_count(self, manager: CacheManager):
        """Each status entry should have is_fresh and record_count."""
        status = manager.status()
        for name, info in status.items():
            assert "is_fresh" in info
            assert "record_count" in info

    @pytest.mark.asyncio
    async def test_status_reflects_fetched_data(self, manager: CacheManager):
        """After fetching, status should reflect freshness and count."""
        async def fetcher():
            return [1, 2, 3]

        await manager.get("test_slot", fetcher)
        status = manager.status()
        assert status["test_slot"]["is_fresh"] is True
        assert status["test_slot"]["record_count"] == 3

    def test_sources_list_returns_list(self, manager: CacheManager):
        """sources_list() should return a list of dicts."""
        sources = manager.sources_list()
        assert isinstance(sources, list)
        assert len(sources) == 2  # test_slot + events

    def test_sources_list_structure(self, manager: CacheManager):
        """Each source should have all expected fields."""
        sources = manager.sources_list()
        expected_keys = {
            "name", "source_url", "ttl_seconds",
            "last_updated", "record_count", "is_cached",
            "is_fresh", "last_error",
        }
        for source in sources:
            assert expected_keys.issubset(source.keys())

    @pytest.mark.asyncio
    async def test_sources_list_reflects_cached_state(self, manager: CacheManager):
        """After a successful fetch, sources should show is_cached=True."""
        async def fetcher():
            return [1]

        await manager.get("test_slot", fetcher)
        sources = manager.sources_list()
        test_source = next(s for s in sources if s["name"] == "test_slot")
        assert test_source["is_cached"] is True
        assert test_source["is_fresh"] is True
        assert test_source["record_count"] == 1
        assert test_source["last_updated"] is not None

    @pytest.mark.asyncio
    async def test_prefetch_all(self, manager: CacheManager):
        """prefetch_all() should fetch all registered slots."""
        call_names = []

        async def make_fetcher(name):
            async def f():
                call_names.append(name)
                return [name]
            return f

        registry = {}
        for name in ["test_slot", "events"]:
            registry[name] = await make_fetcher(name)

        await manager.prefetch_all(registry)
        assert "test_slot" in call_names
        assert "events" in call_names

    @pytest.mark.asyncio
    async def test_concurrent_gets_only_fetch_once(self, manager: CacheManager):
        """Multiple concurrent get() calls should only trigger one fetch."""
        call_count = 0

        async def slow_fetcher():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return [{"id": "data"}]

        # Launch multiple concurrent gets
        results = await asyncio.gather(
            manager.get("test_slot", slow_fetcher),
            manager.get("test_slot", slow_fetcher),
            manager.get("test_slot", slow_fetcher),
        )
        # The lock should prevent more than one actual fetch
        assert call_count == 1
        for result in results:
            assert result == [{"id": "data"}]
