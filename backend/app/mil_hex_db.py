"""
Agus OSINT Backend -- Military Aircraft Database & Enrichment
================================================================
Curated military ICAO hex ranges from tar1090-db (Mictronics) plus
hexdb.io API enrichment for aircraft owner/operator/type details.
"""

from __future__ import annotations

import logging
import time
from typing import ClassVar, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("agus.mil_db")

# ---------------------------------------------------------------------------
# Known military ICAO24 hex ranges (from tar1090-db / Mictronics database)
# Format: (start_hex, end_hex, country, branch)
# ---------------------------------------------------------------------------
MILITARY_HEX_RANGES: List[Tuple[str, str, str, str]] = [
    # United States Department of Defense
    ("adf7c0", "afffff", "United States", "US DoD"),
    ("ae0000", "aeffff", "United States", "US DoD"),
    # United States Coast Guard
    ("a9f000", "a9ffff", "United States", "USCG"),
    # United Kingdom Military
    ("43c000", "43cfff", "United Kingdom", "UK Military"),
    # France Military
    ("3a0000", "3affff", "France", "French Military"),
    # Germany Military
    ("3f0000", "3fffff", "Germany", "German Military"),
    # Italy Military
    ("300000", "303fff", "Italy", "Italian Military"),
    # Spain Military
    ("340000", "343fff", "Spain", "Spanish Military"),
    # Turkey Military
    ("4b8000", "4bffff", "Turkey", "Turkish Military"),
    # Israel Military
    ("738000", "73ffff", "Israel", "Israeli Military"),
    # Russia Military
    ("150000", "157fff", "Russia", "Russian Military"),
    # China Military
    ("780000", "783fff", "China", "Chinese Military"),
    # India Military
    ("800000", "803fff", "India", "Indian Military"),
    # Japan Self-Defense Forces
    ("840000", "843fff", "Japan", "JASDF"),
    # South Korea Military
    ("718000", "71bfff", "South Korea", "ROKAF"),
    # Australia Military
    ("7c8000", "7cbfff", "Australia", "RAAF"),
    # Canada Military
    ("c2c000", "c2cfff", "Canada", "Canadian Forces"),
    # Norway Military (must be before NATO — sub-range)
    ("478000", "47bfff", "Norway", "Norwegian Military"),
    # Greece Military
    ("468000", "46bfff", "Greece", "Greek Military"),
    # NATO (various — catch-all for remaining 47C000-47FFFF)
    ("478000", "47ffff", "NATO", "NATO"),
    # Saudi Arabia Military
    ("710000", "713fff", "Saudi Arabia", "RSAF"),
    # UAE Military
    ("896000", "897fff", "UAE", "UAE Military"),
    # Egypt Military
    ("500000", "503fff", "Egypt", "Egyptian Military"),
    # Pakistan Military
    ("760000", "763fff", "Pakistan", "Pakistan Military"),
    # Brazil Military
    ("e94000", "e97fff", "Brazil", "Brazilian Military"),
    # Sweden Military
    ("4a0000", "4a3fff", "Sweden", "Swedish Military"),
    # Netherlands Military
    ("480000", "483fff", "Netherlands", "Dutch Military"),
    # Poland Military
    ("488000", "48bfff", "Poland", "Polish Military"),
]

# Pre-compute integer ranges for fast lookup
_COMPILED_RANGES: List[Tuple[int, int, str, str]] = []
for _start, _end, _country, _branch in MILITARY_HEX_RANGES:
    _COMPILED_RANGES.append((int(_start, 16), int(_end, 16), _country, _branch))


def is_military_hex(hex_code: str) -> Optional[Tuple[str, str]]:
    """Check if an ICAO24 hex code falls within a known military range.

    Args:
        hex_code: 6-character hex string.

    Returns:
        (country, branch) tuple if military, or None.
    """
    if not hex_code or len(hex_code) < 4:
        return None
    try:
        val = int(hex_code.lower().strip(), 16)
    except ValueError:
        return None
    for start, end, country, branch in _COMPILED_RANGES:
        if start <= val <= end:
            return (country, branch)
    return None


# ---------------------------------------------------------------------------
# hexdb.io enrichment cache
# ---------------------------------------------------------------------------
_HEXDB_CACHE: Dict[str, dict] = {}
_HEXDB_CACHE_TIME: Dict[str, float] = {}
_HEXDB_TTL = 3600.0  # 1 hour cache per hex
_HEXDB_BATCH_SIZE = 20  # Max concurrent lookups per cycle
_HEXDB_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


async def enrich_from_hexdb(
    client: httpx.AsyncClient, hex_codes: List[str],
) -> Dict[str, dict]:
    """Batch-lookup aircraft details from hexdb.io API.

    Returns cached results where available, fetches missing ones.
    Rate-limited to _HEXDB_BATCH_SIZE concurrent requests.

    Args:
        client: httpx client.
        hex_codes: List of ICAO24 hex codes to look up.

    Returns:
        Dict mapping hex_code -> {Registration, RegisteredOwners, Type,
        Manufacturer, OperatorFlagCode, ICAOTypeCode}.
    """
    import asyncio

    results: Dict[str, dict] = {}
    now = time.monotonic()
    to_fetch: List[str] = []

    for hx in hex_codes:
        hx = hx.lower().strip()
        if hx in _HEXDB_CACHE and (now - _HEXDB_CACHE_TIME.get(hx, 0)) < _HEXDB_TTL:
            results[hx] = _HEXDB_CACHE[hx]
        else:
            to_fetch.append(hx)

    if not to_fetch:
        return results

    # Limit to batch size to avoid hammering the API
    to_fetch = to_fetch[:_HEXDB_BATCH_SIZE]

    async def _lookup(hx: str) -> None:
        try:
            resp = await client.get(
                f"https://hexdb.io/api/v1/aircraft/{hx}",
                timeout=_HEXDB_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                _HEXDB_CACHE[hx] = data
                _HEXDB_CACHE_TIME[hx] = time.monotonic()
                results[hx] = data
            else:
                # Cache empty result to avoid re-fetching
                _HEXDB_CACHE[hx] = {}
                _HEXDB_CACHE_TIME[hx] = time.monotonic()
        except Exception:
            pass  # Silently skip on error

    await asyncio.gather(*[_lookup(hx) for hx in to_fetch], return_exceptions=True)
    return results


def format_enrichment(hexdb_data: dict) -> dict:
    """Format hexdb.io response into display-friendly fields.

    Args:
        hexdb_data: Raw response from hexdb.io API.

    Returns:
        Dict with formatted enrichment fields.
    """
    if not hexdb_data:
        return {}
    return {
        "registration": hexdb_data.get("Registration", ""),
        "owner": hexdb_data.get("RegisteredOwners", ""),
        "aircraft_model": hexdb_data.get("Type", ""),
        "manufacturer": hexdb_data.get("Manufacturer", ""),
        "operator_code": hexdb_data.get("OperatorFlagCode", ""),
        "icao_type": hexdb_data.get("ICAOTypeCode", ""),
    }
