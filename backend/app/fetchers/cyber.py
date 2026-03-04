"""AbuseIPDB and Tor Project cyber threat fetcher — all live data."""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timezone
from typing import List

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")


class CyberFetcher(BaseFetcher):
    """Fetches cyber threat intelligence from AbuseIPDB + Tor exit nodes."""

    async def _from_abuseipdb(self, client: httpx.AsyncClient) -> List[dict]:
        key = os.getenv("ABUSEIPDB_API_KEY", "")
        if not key:
            return []
        resp = await client.get(
            "https://api.abuseipdb.com/api/v2/blacklist",
            headers={"Key": key, "Accept": "application/json"},
            params={"limit": 200, "confidenceMinimum": 90}, timeout=15.0,
        )
        resp.raise_for_status()
        abuse_data = resp.json().get("data") or []
        ips = [ip["ipAddress"] for ip in abuse_data[:50] if ip.get("ipAddress")]
        if not ips:
            return []
        geo_resp = await client.post(
            "http://ip-api.com/batch?fields=status,country,countryCode,city,lat,lon,isp,query",
            json=[{"query": ip} for ip in ips], timeout=10.0,
        )
        geo_resp.raise_for_status()
        now_iso = datetime.now(timezone.utc).isoformat()
        results: List[dict] = []
        for i, geo in enumerate(geo_resp.json()):
            if geo.get("status") != "success":
                continue
            lat, lon = geo.get("lat"), geo.get("lon")
            if lat is None or lon is None:
                continue
            score = abuse_data[i].get("abuseConfidenceScore", 0) if i < len(abuse_data) else 0
            results.append({
                "title": f"Threat: {geo.get('query', 'Unknown IP')}",
                "latitude": lat, "longitude": lon, "type": "malicious_ip",
                "severity": "high" if score >= 95 else "medium",
                "target_country": geo.get("country", ""),
                "city": geo.get("city", ""), "isp": geo.get("isp", ""),
                "confidence": score, "date": now_iso, "source": "AbuseIPDB",
            })
        return results

    async def _from_tor(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch live Tor exit node list and geolocate a sample."""
        resp = await client.get(
            "https://check.torproject.org/torbulkexitlist",
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
        )
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        all_ips = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
        if not all_ips:
            return []

        # Sample up to 30 exit nodes and geolocate them live
        sample = random.sample(all_ips, min(30, len(all_ips)))
        try:
            geo_resp = await client.post(
                "http://ip-api.com/batch?fields=query,lat,lon,country,city,isp,status",
                json=[{"query": ip} for ip in sample],
                timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            )
            geo_resp.raise_for_status()
        except Exception as exc:
            logger.warning("Tor geolocate failed: %s", exc)
            return []

        now_iso = datetime.now(timezone.utc).isoformat()
        results: List[dict] = []
        for geo in geo_resp.json():
            if geo.get("status") != "success":
                continue
            lat, lon = geo.get("lat"), geo.get("lon")
            if lat is None or lon is None:
                continue
            results.append({
                "title": f"Tor Exit: {geo.get('query', '?')}",
                "latitude": lat, "longitude": lon,
                "type": "tor_exit_node",
                "severity": "info",
                "target_country": geo.get("country", ""),
                "city": geo.get("city", ""),
                "isp": geo.get("isp", ""),
                "date": now_iso,
                "source": "Tor Project",
            })

        logger.info("Tor: geolocated %d/%d exit nodes (total: %d)",
                     len(results), len(sample), len(all_ips))
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._collect(client, self._from_abuseipdb, self._from_tor)
