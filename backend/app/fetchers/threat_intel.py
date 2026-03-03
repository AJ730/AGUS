"""Threat intelligence fetcher — AlienVault OTX pulses + Shodan InternetDB."""

from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import List

import httpx

from ..utils import COUNTRY_COORDS
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_OTX_KEY = os.getenv("OTX_API_KEY", "")

# Well-known Tor exit nodes (sample IPs for Shodan InternetDB enrichment)
_TOR_SEED_IPS = [
    "185.220.101.1", "185.220.101.2", "185.220.101.3", "185.220.101.4",
    "185.220.101.5", "185.220.101.6", "185.220.101.7", "185.220.101.8",
    "185.220.101.9", "185.220.101.10", "185.220.101.11", "185.220.101.12",
    "185.220.101.13", "185.220.101.14", "185.220.101.15", "185.220.101.16",
    "185.220.101.17", "185.220.101.18", "185.220.101.19", "185.220.101.20",
    "185.220.101.21", "185.220.101.22", "185.220.101.23", "185.220.101.24",
    "185.220.101.25", "185.220.101.26", "185.220.101.27", "185.220.101.28",
    "185.220.101.29", "185.220.101.30", "185.220.101.31", "185.220.101.32",
    "198.98.51.189", "199.195.250.77", "209.141.34.95", "23.129.64.130",
    "23.129.64.131", "23.129.64.132", "23.129.64.133", "23.129.64.134",
]


class ThreatIntelFetcher(BaseFetcher):
    """Combines AlienVault OTX pulse indicators with Shodan InternetDB data."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        return await self._collect(client, self._from_otx, self._from_shodan_internetdb)

    # ------------------------------------------------------------------
    # AlienVault OTX
    # ------------------------------------------------------------------
    async def _from_otx(self, client: httpx.AsyncClient) -> List[dict]:
        results: List[dict] = []
        try:
            headers = {"Accept": "application/json"}
            if _OTX_KEY:
                headers["X-OTX-API-KEY"] = _OTX_KEY
                url = "https://otx.alienvault.com/api/v1/pulses/subscribed"
            else:
                url = "https://otx.alienvault.com/api/v1/pulses/activity"

            resp = await client.get(
                url,
                headers=headers,
                params={"limit": 20, "page": 1},
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0),
            )
            resp.raise_for_status()
            pulses = resp.json().get("results") or []

            ipv4_indicators: List[dict] = []
            country_indicators: List[dict] = []

            for pulse in pulses[:20]:
                title = pulse.get("name", "Unknown Pulse")
                severity = _pulse_severity(pulse)
                targeted = pulse.get("targeted_countries") or []

                for ioc in (pulse.get("indicators") or [])[:50]:
                    ioc_type = ioc.get("type", "")
                    indicator = ioc.get("indicator", "")
                    if ioc_type == "IPv4":
                        ipv4_indicators.append({
                            "title": title,
                            "indicator": indicator,
                            "indicator_type": "IPv4",
                            "severity": severity,
                            "source": "AlienVault OTX",
                        })
                    elif targeted:
                        for cc in targeted[:3]:
                            country_indicators.append({
                                "title": title,
                                "indicator": indicator,
                                "indicator_type": ioc_type,
                                "severity": severity,
                                "source": "AlienVault OTX",
                                "country_code": cc.upper(),
                            })

                # If pulse has targeted countries but no IP indicators, add country-level
                if targeted and not any(i.get("type") == "IPv4" for i in (pulse.get("indicators") or [])):
                    for cc in targeted[:3]:
                        country_indicators.append({
                            "title": title,
                            "indicator": "pulse",
                            "indicator_type": "pulse",
                            "severity": severity,
                            "source": "AlienVault OTX",
                            "country_code": cc.upper(),
                        })

            # Batch geolocate IPv4 indicators
            if ipv4_indicators:
                ips = list({i["indicator"] for i in ipv4_indicators})[:100]
                geo_map = await _batch_geolocate(client, ips)
                for item in ipv4_indicators:
                    loc = geo_map.get(item["indicator"])
                    if loc:
                        item["latitude"] = loc[0]
                        item["longitude"] = loc[1]
                        item["country"] = loc[2]
                        results.append(item)

            # Geocode country-level indicators via COUNTRY_COORDS
            for item in country_indicators:
                cc = item.pop("country_code", "")
                coords = COUNTRY_COORDS.get(cc) or COUNTRY_COORDS.get(cc.lower())
                if coords:
                    item["latitude"] = coords[0] + random.uniform(-1.5, 1.5)
                    item["longitude"] = coords[1] + random.uniform(-1.5, 1.5)
                    item["country"] = cc
                    results.append(item)

        except Exception as exc:
            logger.warning("OTX fetch failed: %s", exc)

        return results

    # ------------------------------------------------------------------
    # Shodan InternetDB
    # ------------------------------------------------------------------
    async def _from_shodan_internetdb(self, client: httpx.AsyncClient) -> List[dict]:
        results: List[dict] = []
        sample_ips = random.sample(_TOR_SEED_IPS, min(20, len(_TOR_SEED_IPS)))

        async def _query_one(ip: str) -> dict | None:
            try:
                resp = await client.get(
                    f"https://internetdb.shodan.io/{ip}",
                    timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
            return None

        tasks = [_query_one(ip) for ip in sample_ips]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        ips_to_geolocate = []
        shodan_data = {}
        for ip, result in zip(sample_ips, raw_results):
            if isinstance(result, dict) and result.get("ip"):
                shodan_data[ip] = result
                ips_to_geolocate.append(ip)

        if ips_to_geolocate:
            geo_map = await _batch_geolocate(client, ips_to_geolocate)
            for ip in ips_to_geolocate:
                data = shodan_data[ip]
                loc = geo_map.get(ip)
                if loc:
                    cves = data.get("vulns") or []
                    ports = data.get("ports") or []
                    severity = "critical" if len(cves) > 5 else "high" if cves else "medium"
                    results.append({
                        "title": f"Exposed host: {ip}",
                        "indicator": ip,
                        "indicator_type": "IPv4",
                        "severity": severity,
                        "source": "Shodan InternetDB",
                        "latitude": loc[0],
                        "longitude": loc[1],
                        "country": loc[2],
                        "open_ports": ports[:10],
                        "cves": cves[:10],
                        "hostnames": (data.get("hostnames") or [])[:5],
                    })

        return results


def _pulse_severity(pulse: dict) -> str:
    """Estimate severity from OTX pulse metadata."""
    tags = " ".join(pulse.get("tags") or []).lower()
    if any(w in tags for w in ("apt", "ransomware", "critical", "zero-day", "0day")):
        return "critical"
    if any(w in tags for w in ("malware", "exploit", "backdoor", "trojan")):
        return "high"
    if any(w in tags for w in ("phishing", "spam", "suspicious")):
        return "medium"
    return "low"


async def _batch_geolocate(client: httpx.AsyncClient, ips: list) -> dict:
    """Batch geolocate IPs using ip-api.com (free, 100/min, supports batch)."""
    geo: dict = {}
    # ip-api.com batch endpoint accepts up to 100 IPs
    batch = [{"query": ip} for ip in ips[:100]]
    try:
        resp = await client.post(
            "http://ip-api.com/batch?fields=query,lat,lon,country,status",
            json=batch,
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
        )
        resp.raise_for_status()
        for item in resp.json():
            if item.get("status") == "success":
                geo[item["query"]] = (item["lat"], item["lon"], item.get("country", ""))
    except Exception as exc:
        logger.warning("ip-api batch geolocate failed: %s", exc)
    return geo
