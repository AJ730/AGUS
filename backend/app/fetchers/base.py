"""Base classes and shared HTTP helpers for OSINT fetchers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("agus.fetchers")

_WD_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=5.0, pool=10.0)
_OP_TIMEOUT = httpx.Timeout(connect=10.0, read=100.0, write=10.0, pool=10.0)


class BaseFetcher(ABC):
    """Abstract base with reusable helpers for Wikidata, GDELT, Overpass."""

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> Any:
        ...

    async def _try_sources(self, client: httpx.AsyncClient,
                           *fns: Callable) -> list:
        """Try source functions in order; return first non-empty result."""
        for fn in fns:
            try:
                result = await fn(client)
                if result:
                    return result
            except Exception as exc:
                logger.warning("%s: %s", fn.__name__, exc)
        return []

    async def _collect(self, client: httpx.AsyncClient,
                       *fns: Callable) -> list:
        """Run all source functions, combining results additively."""
        results: list = []
        for fn in fns:
            try:
                results.extend(await fn(client))
            except Exception as exc:
                logger.warning("%s: %s", fn.__name__, exc)
        return results

    @staticmethod
    async def _wikidata(client: httpx.AsyncClient, sparql: str) -> list:
        """Run Wikidata SPARQL query, return result bindings."""
        resp = await client.get(
            "https://query.wikidata.org/sparql",
            params={"format": "json", "query": sparql.strip()},
            headers={"User-Agent": "AgusOSINT/1.0",
                     "Accept": "application/json"},
            timeout=_WD_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("results", {}).get("bindings", [])

    @staticmethod
    def _coords(b: dict) -> Optional[Tuple[float, float]]:
        """Extract (lat, lon) from a Wikidata binding, or None on bad data."""
        try:
            return float(b["lat"]["value"]), float(b["lon"]["value"])
        except (ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def _label(b: dict, field: str, default: str = "") -> str:
        """Extract a label string from a Wikidata binding."""
        return b.get(field, {}).get("value", default)

    @staticmethod
    async def _gdelt(client: httpx.AsyncClient, query: str,
                     timespan: str = "7D", maxrows: int = 500) -> list:
        """Fetch GDELT GEO features (HTTP for Docker compatibility)."""
        from urllib.parse import quote
        encoded_query = quote(query, safe="")
        url = (f"http://api.gdeltproject.org/api/v2/geo/geo"
               f"?query={encoded_query}&format=GeoJSON"
               f"&TIMESPAN={timespan}&maxrows={maxrows}")
        resp = await client.get(url, timeout=30.0)
        resp.raise_for_status()
        return resp.json().get("features") or []

    @staticmethod
    async def _overpass(client: httpx.AsyncClient, query: str) -> list:
        """Execute Overpass API query, return elements."""
        resp = await client.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query}, timeout=_OP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("elements") or []


class FetcherRegistry:
    """Maps layer names to fetcher instances."""

    def __init__(self) -> None:
        self._fetchers: Dict[str, BaseFetcher] = {}

    def register(self, name: str, fetcher: BaseFetcher) -> None:
        self._fetchers[name] = fetcher

    def get(self, name: str) -> BaseFetcher:
        return self._fetchers[name]

    def names(self) -> List[str]: return list(self._fetchers.keys())
    def items(self) -> list: return list(self._fetchers.items())
