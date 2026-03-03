"""OpenSanctions international sanctions data fetcher."""

from __future__ import annotations

import csv
import io
import logging
from typing import Dict, List

import httpx

from ..utils import COUNTRY_COORDS
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_URL = "https://data.opensanctions.org/datasets/latest/default/targets.simple.csv"


class SanctionsFetcher(BaseFetcher):
    """Fetches international sanctions data from OpenSanctions bulk CSV.

    Streams the 458MB CSV line-by-line to avoid loading it all into memory.
    """

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        try:
            country_counts: Dict[str, dict] = {}
            header: list = []
            async with client.stream(
                "GET", _URL,
                timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    # Parse with csv.reader to handle quoted fields
                    parsed = list(csv.reader(io.StringIO(line)))
                    if not parsed or not parsed[0]:
                        continue
                    fields = parsed[0]
                    if not header:
                        header = fields
                        continue
                    field_map = {
                        header[i]: fields[i] if i < len(fields) else ""
                        for i in range(len(header))
                    }
                    countries_str = field_map.get("countries", "")
                    if not countries_str:
                        continue
                    datasets = field_map.get("datasets", "")
                    first_seen = field_map.get("first_seen", "")
                    for cc in countries_str.split(";"):
                        cc = cc.strip()
                        if not cc:
                            continue
                        if cc not in country_counts:
                            country_counts[cc] = {
                                "count": 0, "datasets": set(),
                                "first_seen": first_seen,
                            }
                        country_counts[cc]["count"] += 1
                        for ds in (datasets or "").split(";"):
                            ds = ds.strip()
                            if ds:
                                country_counts[cc]["datasets"].add(ds)

            results: List[dict] = []
            for cc, info in country_counts.items():
                lat, lon = COUNTRY_COORDS.get(cc.lower(), (0.0, 0.0))
                if lat == 0 and lon == 0:
                    lat, lon = COUNTRY_COORDS.get(
                        cc, COUNTRY_COORDS.get(cc.upper(), (0.0, 0.0)))
                if lat == 0 and lon == 0:
                    continue
                results.append({
                    "country": cc, "latitude": lat, "longitude": lon,
                    "sanction_type": "targeted",
                    "imposed_by": ", ".join(sorted(info["datasets"]))[:200],
                    "date": info["first_seen"],
                    "details": f"{info['count']} sanctioned entities",
                })
            return results
        except Exception as exc:
            logger.warning("OpenSanctions fetch failed: %s", exc)
        return []
