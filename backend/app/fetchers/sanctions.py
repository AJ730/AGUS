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
    """Fetches international sanctions data from OpenSanctions bulk CSV."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        try:
            resp = await client.get(
                _URL,
                timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
            )
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            country_counts: Dict[str, dict] = {}
            for row in reader:
                countries_str = row.get("countries", "")
                if not countries_str:
                    continue
                datasets = row.get("datasets", "")
                first_seen = row.get("first_seen", "")
                for cc in countries_str.split(";"):
                    cc = cc.strip()
                    if not cc:
                        continue
                    if cc not in country_counts:
                        country_counts[cc] = {"count": 0, "datasets": set(),
                                              "first_seen": first_seen}
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
