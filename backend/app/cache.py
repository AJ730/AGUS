"""
Agus OSINT Backend -- Cache Infrastructure
===============================================
Thread-safe in-memory cache with per-slot TTL-based invalidation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger("agus.cache")


@dataclass
class CacheEntry:
    """Single cached response with metadata."""
    data: Any = None
    fetched_at: float = 0.0          # monotonic clock (for TTL checks)
    fetched_at_wall: float = 0.0     # wall clock / Unix epoch (for display)
    record_count: int = 0
    error: Optional[str] = None


@dataclass
class HistorySnapshot:
    """A timestamped snapshot of layer data for timeline scrubbing."""
    wall_ts: float           # Unix epoch timestamp
    record_count: int
    data: Any


# Layers eligible for historical snapshots (OSINT / event layers, not real-time)
HISTORY_LAYERS = frozenset({
    "conflicts", "earthquakes", "missile_tests", "rocket_alerts",
    "telegram_osint", "reddit_osint", "news", "events", "terrorism",
    "fires", "weather_alerts", "geo_confirmed", "equipment_losses",
    "internet_outages", "gps_jamming", "natural_events",
})

MAX_SNAPSHOTS_PER_LAYER = 48  # ~24h at 30min intervals


@dataclass
class CacheSlot:
    """A named cache slot with its own TTL."""
    name: str
    ttl_seconds: float
    source_url: str
    entry: CacheEntry = field(default_factory=CacheEntry)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def is_fresh(self) -> bool:
        if self.entry.fetched_at == 0.0:
            return False
        return (time.monotonic() - self.entry.fetched_at) < self.ttl_seconds

    @property
    def last_updated_iso(self) -> Optional[str]:
        if self.entry.fetched_at_wall == 0.0:
            return None
        return datetime.fromtimestamp(
            self.entry.fetched_at_wall, tz=timezone.utc
        ).isoformat()


class CacheManager:
    """Thread-safe cache manager with TTL-based invalidation."""

    def __init__(self) -> None:
        self._slots: Dict[str, CacheSlot] = {}
        self._history: Dict[str, deque] = {}

    def register(self, name: str, ttl: float, source_url: str) -> None:
        """Register a new cache slot."""
        self._slots[name] = CacheSlot(
            name=name,
            ttl_seconds=ttl,
            source_url=source_url,
        )
        if name in HISTORY_LAYERS:
            self._history[name] = deque(maxlen=MAX_SNAPSHOTS_PER_LAYER)

    def slot(self, name: str) -> CacheSlot:
        """Return the named CacheSlot (for header inspection etc.)."""
        return self._slots[name]

    async def get(
        self,
        name: str,
        fetcher_fn: Callable[[], Coroutine[Any, Any, Any]],
    ) -> Any:
        """
        Return data from the named cache slot.  If stale, refresh via
        *fetcher_fn*.  Never raises -- on error returns whatever we had
        last, or an empty list / feature collection.
        """
        slot = self._slots[name]

        if slot.is_fresh and slot.entry.data is not None:
            return slot.entry.data

        async with slot.lock:
            # Double-check after acquiring the lock.
            if slot.is_fresh and slot.entry.data is not None:
                return slot.entry.data

            try:
                logger.info(
                    "Fetching fresh data for [%s] from %s", name, slot.source_url
                )
                data = await fetcher_fn()
                count = len(data) if isinstance(data, list) else (
                    len((data or {}).get("features", []))
                    if isinstance(data, dict) else 0
                )
                now = time.monotonic()
                prev_data = slot.entry.data
                prev_count = slot.entry.record_count

                # If fetcher returned empty but we have good prior data,
                # keep the previous data and use a short TTL to retry.
                if count == 0 and prev_data and prev_count > 0:
                    backoff_ttl = 30.0
                    fetched_at = now - slot.ttl_seconds + backoff_ttl
                    logger.info("[%s] empty refetch, keeping %d prior records (retry in %.0fs)",
                                name, prev_count, backoff_ttl)
                    slot.entry.fetched_at = fetched_at
                    slot.entry.error = None
                elif count == 0 and prev_data in (None, [], {"type": "FeatureCollection", "features": []}):
                    # No prior data either -- short backoff retry
                    backoff_ttl = 30.0
                    fetched_at = now - slot.ttl_seconds + backoff_ttl
                    logger.info("[%s] empty result, will retry in %.0fs", name, backoff_ttl)
                    slot.entry = CacheEntry(
                        data=data, fetched_at=fetched_at,
                        fetched_at_wall=time.time(), record_count=count,
                    )
                else:
                    fetched_at = now
                    slot.entry = CacheEntry(
                        data=data, fetched_at=fetched_at,
                        fetched_at_wall=time.time(), record_count=count,
                    )
                logger.info("[%s] refreshed -- %d records", name, count)

                # Record history snapshot for timeline-eligible layers
                if name in self._history and count > 0:
                    ring = self._history[name]
                    # Only store if record count changed from last snapshot
                    if not ring or ring[-1].record_count != count:
                        ring.append(HistorySnapshot(
                            wall_ts=time.time(),
                            record_count=count,
                            data=data,
                        ))
            except Exception as exc:
                logger.error("[%s] fetch failed: %s", name, exc)
                slot.entry.error = str(exc)
                if slot.entry.data is not None:
                    return slot.entry.data
                if name == "events":
                    return {"type": "FeatureCollection", "features": []}
                return []

        return slot.entry.data

    async def prefetch_all(
        self,
        fetcher_registry: Dict[str, Callable[[], Coroutine[Any, Any, Any]]],
    ) -> None:
        """Fetch sources in staggered waves to avoid rate-limiting.

        Batched to avoid saturating the event loop so health checks can pass.
        """
        # Wave 1a: Quick API sources (small responses, fast)
        wave1a = ["earthquakes", "weather_alerts", "cyber", "refugees",
                  "threat_intel", "signals", "satellites",
                  "reddit_osint", "telegram_osint", "live_streams",
                  "rocket_alerts", "natural_events"]
        # Wave 1b: Medium sources (Wikidata SPARQL, moderate size)
        wave1b = ["vessels", "nuclear", "submarines", "carriers",
                  "sanctions", "undersea_cables", "geo_confirmed",
                  "gps_jamming", "equipment_losses", "internet_outages"]
        # Wave 1c: Heavy sources (large CSVs, multiple API calls)
        wave1c = ["fires", "airports", "flights"]
        # Wave 2: GDELT-dependent sources (stagger to avoid rate limits)
        wave2 = ["events", "conflicts", "cctv", "terrorism", "piracy",
                 "airspace", "notams", "military_bases", "news",
                 "missile_tests"]

        for label, wave in [("1a-quick", wave1a), ("1b-medium", wave1b),
                            ("1c-heavy", wave1c)]:
            tasks = [self.get(n, fetcher_registry[n]) for n in wave
                     if n in self._slots and n in fetcher_registry]
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("Wave %s prefetch complete", label)
            await asyncio.sleep(0.5)  # yield to event loop for health checks

        # Stagger GDELT sources with 2s delay between each
        for name in wave2:
            if name in self._slots and name in fetcher_registry:
                await self.get(name, fetcher_registry[name])
                await asyncio.sleep(2.0)
        logger.info("Wave 2 prefetch complete (GDELT sources)")

    def status(self) -> dict:
        """Return a summary dict suitable for /api/health."""
        return {
            name: {
                "is_fresh": slot.is_fresh,
                "record_count": slot.entry.record_count,
            }
            for name, slot in self._slots.items()
        }

    def get_history(self, name: str, hours: float = 24.0) -> List[Dict[str, Any]]:
        """Return timestamped snapshots for a layer within a time window."""
        ring = self._history.get(name)
        if not ring:
            return []
        cutoff = time.time() - hours * 3600
        result = []
        for snap in ring:
            if snap.wall_ts >= cutoff:
                result.append({
                    "ts": snap.wall_ts,
                    "iso": datetime.fromtimestamp(snap.wall_ts, tz=timezone.utc).isoformat(),
                    "record_count": snap.record_count,
                    "data": snap.data,
                })
        return result

    def history_summary(self) -> Dict[str, Any]:
        """Return available time ranges per history-eligible layer."""
        summary: Dict[str, Any] = {}
        for name, ring in self._history.items():
            if not ring:
                summary[name] = {"snapshots": 0}
                continue
            summary[name] = {
                "snapshots": len(ring),
                "oldest": datetime.fromtimestamp(ring[0].wall_ts, tz=timezone.utc).isoformat(),
                "newest": datetime.fromtimestamp(ring[-1].wall_ts, tz=timezone.utc).isoformat(),
                "oldest_ts": ring[0].wall_ts,
                "newest_ts": ring[-1].wall_ts,
            }
        return summary

    def sources_list(self) -> list:
        """Return detailed list suitable for /api/sources."""
        result = []
        for name, slot in self._slots.items():
            result.append({
                "name": name,
                "source_url": slot.source_url,
                "ttl_seconds": slot.ttl_seconds,
                "last_updated": slot.last_updated_iso,
                "record_count": slot.entry.record_count,
                "is_cached": slot.entry.data is not None,
                "is_fresh": slot.is_fresh,
                "last_error": slot.entry.error,
            })
        return result
