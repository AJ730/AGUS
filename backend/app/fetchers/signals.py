"""Radio/signals intelligence fetcher — KiwiSDR public receiver directory."""

from __future__ import annotations

import json
import logging
import re
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_KIWISDR_URL = "http://rx.linkfanel.net/kiwisdr_com.js"


class SignalsFetcher(BaseFetcher):
    """Fetches worldwide SDR receiver locations from KiwiSDR community directory."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._try_sources(client, self._from_kiwisdr)

    async def _from_kiwisdr(self, client: httpx.AsyncClient) -> List[dict]:
        results: List[dict] = []
        try:
            resp = await client.get(
                _KIWISDR_URL,
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0),
            )
            resp.raise_for_status()
            text = resp.text

            # The JS file contains: var kiwisdr_com = [...];
            match = re.search(r"var\s+kiwisdr_com\s*=\s*\n(\[[\s\S]+\])\s*\n;", text)
            if not match:
                logger.warning("KiwiSDR: could not parse JS array")
                return []

            raw = match.group(1)
            # Fix trailing commas (JS allows them, JSON does not)
            raw = re.sub(r",\s*([}\]])", r"\1", raw)

            try:
                receivers = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("KiwiSDR: JSON decode failed")
                return []

            for rx in receivers:
                try:
                    gps = rx.get("gps") or rx.get("loc") or ""
                    if isinstance(gps, str) and "," in gps:
                        parts = gps.replace("(", "").replace(")", "").split(",")
                        lat = float(parts[0].strip())
                        lon = float(parts[1].strip())
                    elif isinstance(gps, (list, tuple)) and len(gps) >= 2:
                        lat, lon = float(gps[0]), float(gps[1])
                    else:
                        continue

                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        continue

                    name = rx.get("name") or rx.get("id") or "KiwiSDR"
                    url = rx.get("url") or ""
                    if url and not url.startswith("http"):
                        url = "http://" + url

                    freq_lo = rx.get("lo") or rx.get("freq_lo") or 0
                    freq_hi = rx.get("hi") or rx.get("freq_hi") or 30000

                    results.append({
                        "name": str(name)[:100],
                        "location": rx.get("loc") or rx.get("location") or "",
                        "latitude": lat,
                        "longitude": lon,
                        "frequency_range": f"{freq_lo}-{freq_hi} kHz",
                        "url": url,
                        "users": rx.get("users") or 0,
                        "users_max": rx.get("users_max") or 0,
                        "antenna": rx.get("ant") or rx.get("antenna") or "",
                        "type": "sdr_receiver",
                        "source": "KiwiSDR",
                    })
                except (ValueError, TypeError, IndexError):
                    continue

            logger.info("KiwiSDR: fetched %d receivers", len(results))
        except Exception as exc:
            logger.warning("KiwiSDR fetch failed: %s", exc)

        return results
