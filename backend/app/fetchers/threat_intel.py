"""Threat intelligence fetcher — AlienVault OTX + Shodan InternetDB + GreyNoise.

Scans multiple threat intelligence sources:
- AlienVault OTX: APT pulses and IoC feeds
- Shodan InternetDB: Exposed hosts, CVEs, open ports (free, no API key)
- GreyNoise Community: Internet-wide scan noise classification
- Tor exit nodes: Anonymization infrastructure mapping
"""

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
_GREYNOISE_KEY = os.getenv("GREYNOISE_API_KEY", "")

_TOR_EXIT_LIST_URL = "https://check.torproject.org/torbulkexitlist"

# Critical infrastructure IP ranges to scan via Shodan InternetDB
# These are well-known public-facing IPs of interest (gov, defense, energy, telecom)
_CRITICAL_INFRA_DOMAINS = [
    # DNS roots and major resolvers (canary for BGP hijacks)
    "1.1.1.1", "8.8.8.8", "9.9.9.9", "208.67.222.222",
    # ICS/SCADA honeypots and known exposed systems (Shodan indexed)
    "185.220.100.252", "185.220.100.253", "185.220.101.1",
    "185.56.80.65", "185.100.87.174",
]

# Conflict zone country codes for targeted scanning
_CONFLICT_ZONE_COUNTRIES = [
    "IR", "RU", "UA", "IL", "PS", "LB", "SY", "YE", "SD",
    "MM", "KP", "CN", "TW", "ET", "SO", "ML", "NE", "BF",
    "CD", "IQ", "AF", "PK", "LY",
]


class ThreatIntelFetcher(BaseFetcher):
    """Combines AlienVault OTX, Shodan InternetDB, GreyNoise, DShield, Feodo, CISA KEV, and Tor data."""

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch from all threat intelligence sources concurrently."""
        return await self._collect(
            client,
            self._from_otx,
            self._from_shodan_internetdb,
            self._from_greynoise,
            self._from_urlhaus,
            self._from_dshield,
            self._from_feodo_tracker,
            self._from_cisa_kev,
        )

    # ------------------------------------------------------------------
    # AlienVault OTX
    # ------------------------------------------------------------------
    async def _from_otx(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch threat pulses from AlienVault OTX."""
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
                params={"limit": 50, "page": 1},
                timeout=httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=10.0),
            )
            resp.raise_for_status()
            pulses = resp.json().get("results") or []

            ipv4_indicators: List[dict] = []
            country_indicators: List[dict] = []

            for pulse in pulses[:50]:
                title = pulse.get("name", "Unknown Pulse")
                severity = _pulse_severity(pulse)
                targeted = pulse.get("targeted_countries") or []
                tags = pulse.get("tags") or []
                adversary = pulse.get("adversary") or ""

                for ioc in (pulse.get("indicators") or [])[:80]:
                    ioc_type = ioc.get("type", "")
                    indicator = ioc.get("indicator", "")
                    if ioc_type == "IPv4":
                        ipv4_indicators.append({
                            "title": title,
                            "indicator": indicator,
                            "indicator_type": "IPv4",
                            "severity": severity,
                            "source": "AlienVault OTX",
                            "tags": ", ".join(tags[:5]),
                            "adversary": adversary,
                        })
                    elif ioc_type in ("domain", "hostname", "URL"):
                        # Country-level placement for non-IP indicators
                        if targeted:
                            for cc in targeted[:3]:
                                country_indicators.append({
                                    "title": title,
                                    "indicator": indicator,
                                    "indicator_type": ioc_type,
                                    "severity": severity,
                                    "source": "AlienVault OTX",
                                    "country_code": cc.upper(),
                                    "tags": ", ".join(tags[:5]),
                                    "adversary": adversary,
                                })

                # Pulse-level country indicators
                if targeted and not ipv4_indicators:
                    for cc in targeted[:3]:
                        country_indicators.append({
                            "title": title,
                            "indicator": "pulse",
                            "indicator_type": "pulse",
                            "severity": severity,
                            "source": "AlienVault OTX",
                            "country_code": cc.upper(),
                            "tags": ", ".join(tags[:5]),
                            "adversary": adversary,
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

            # Geocode country-level indicators
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

        logger.info("OTX: %d threat indicators", len(results))
        return results

    # ------------------------------------------------------------------
    # Shodan InternetDB (expanded scanning)
    # ------------------------------------------------------------------
    async def _from_shodan_internetdb(self, client: httpx.AsyncClient) -> List[dict]:
        """Scan Tor exit nodes AND critical infrastructure via Shodan InternetDB.

        InternetDB is free, no API key, no rate limit (reasonable use).
        Returns open ports, CVEs, hostnames, and tags for any IP.
        """
        results: List[dict] = []

        # 1. Fetch Tor exit node list
        tor_ips: List[str] = []
        try:
            tor_resp = await client.get(
                _TOR_EXIT_LIST_URL,
                timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            )
            tor_resp.raise_for_status()
            tor_ips = [
                ln.strip() for ln in tor_resp.text.strip().split("\n")
                if ln.strip() and not ln.startswith("#")
            ]
        except Exception as exc:
            logger.warning("Tor exit list fetch failed: %s", exc)

        # 2. Build IP scan list: Tor sample + critical infra + random probes
        scan_ips: List[str] = []

        # Tor exit nodes (sample 30)
        if tor_ips:
            scan_ips.extend(random.sample(tor_ips, min(30, len(tor_ips))))

        # Critical infrastructure IPs
        scan_ips.extend(_CRITICAL_INFRA_DOMAINS)

        # Random IPs in conflict zone ranges (for exposure scanning)
        for _ in range(15):
            # Generate random IPs in common hosting ranges
            first = random.choice([41, 46, 77, 78, 79, 80, 81, 82, 83, 84,
                                   85, 86, 87, 88, 89, 91, 92, 93, 94, 95,
                                   176, 177, 178, 185, 188, 193, 194, 195])
            ip = f"{first}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            scan_ips.append(ip)

        # Deduplicate
        scan_ips = list(dict.fromkeys(scan_ips))[:60]

        # 3. Query Shodan InternetDB concurrently
        async def _query_shodan(ip: str) -> dict | None:
            """Query Shodan InternetDB for a single IP."""
            try:
                resp = await client.get(
                    f"https://internetdb.shodan.io/{ip}",
                    timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ports") or data.get("vulns"):
                        return data
            except Exception:
                pass
            return None

        # Run in batches of 20 to avoid overwhelming connections
        shodan_data: dict = {}
        for i in range(0, len(scan_ips), 20):
            batch = scan_ips[i:i + 20]
            tasks = [_query_shodan(ip) for ip in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for ip, result in zip(batch, batch_results):
                if isinstance(result, dict) and result.get("ip"):
                    shodan_data[ip] = result
            if i + 20 < len(scan_ips):
                await asyncio.sleep(0.5)

        # 4. Geolocate all found IPs
        if shodan_data:
            geo_map = await _batch_geolocate(client, list(shodan_data.keys()))
            for ip, data in shodan_data.items():
                loc = geo_map.get(ip)
                if not loc:
                    continue
                cves = data.get("vulns") or []
                ports = data.get("ports") or []
                hostnames = data.get("hostnames") or []
                tags = data.get("tags") or []

                # Determine source type
                is_tor = ip in tor_ips
                is_critical = ip in _CRITICAL_INFRA_DOMAINS

                # Severity based on CVEs and port exposure
                if len(cves) > 10:
                    severity = "critical"
                elif len(cves) > 3:
                    severity = "high"
                elif cves or len(ports) > 10:
                    severity = "medium"
                else:
                    severity = "low"

                # Build descriptive title
                if is_tor:
                    title = f"Tor Exit Node: {ip}"
                elif is_critical:
                    title = f"Critical Infra: {ip}"
                elif cves:
                    title = f"Vulnerable Host ({len(cves)} CVEs): {ip}"
                else:
                    title = f"Exposed Host ({len(ports)} ports): {ip}"

                results.append({
                    "title": title,
                    "indicator": ip,
                    "indicator_type": "IPv4",
                    "severity": severity,
                    "source": "Shodan InternetDB",
                    "latitude": loc[0],
                    "longitude": loc[1],
                    "country": loc[2],
                    "open_ports": ports[:15],
                    "cves": cves[:15],
                    "hostnames": hostnames[:5],
                    "tags": ", ".join(tags[:5]),
                    "is_tor": is_tor,
                    "is_critical": is_critical,
                })

        logger.info("Shodan InternetDB: %d hosts scanned, %d with results",
                     len(scan_ips), len(results))
        return results

    # ------------------------------------------------------------------
    # GreyNoise Community API (free, classify IPs as benign/malicious/unknown)
    # ------------------------------------------------------------------
    async def _from_greynoise(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch recent malicious scanner activity from GreyNoise RIOT + Community."""
        results: List[dict] = []

        # GreyNoise community API — free, rate limited
        # Query for known malicious scanners targeting critical ports
        critical_tags = [
            "Mirai", "SSH Bruteforce", "HTTP Crawler", "VNC Scanner",
            "RDP Scanner", "SMB Scanner", "Telnet Scanner",
        ]

        try:
            # Use GNQL (GreyNoise Query Language) if we have an API key
            if _GREYNOISE_KEY:
                resp = await client.get(
                    "https://api.greynoise.io/v3/community/search",
                    headers={"key": _GREYNOISE_KEY, "Accept": "application/json"},
                    params={"query": "classification:malicious last_seen:1d", "limit": 50},
                    timeout=httpx.Timeout(connect=10.0, read=20.0, write=5.0, pool=10.0),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ips = [item.get("ip") for item in (data.get("data") or []) if item.get("ip")]
                    if ips:
                        geo_map = await _batch_geolocate(client, ips[:50])
                        for item in (data.get("data") or []):
                            ip = item.get("ip")
                            loc = geo_map.get(ip)
                            if loc:
                                results.append({
                                    "title": f"Scanner: {ip} ({item.get('name', 'Unknown')})",
                                    "indicator": ip,
                                    "indicator_type": "IPv4",
                                    "severity": "high" if item.get("classification") == "malicious" else "medium",
                                    "source": "GreyNoise",
                                    "latitude": loc[0],
                                    "longitude": loc[1],
                                    "country": loc[2],
                                    "tags": item.get("name", ""),
                                })
        except Exception as exc:
            logger.debug("GreyNoise fetch failed: %s", exc)

        return results

    # ------------------------------------------------------------------
    # URLhaus (abuse.ch) — active malware distribution URLs
    # ------------------------------------------------------------------
    async def _from_urlhaus(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch recent malware distribution URLs from URLhaus."""
        results: List[dict] = []
        try:
            resp = await client.get(
                "https://urlhaus-api.abuse.ch/v1/urls/recent/limit/50/",
                timeout=httpx.Timeout(connect=10.0, read=20.0, write=5.0, pool=10.0),
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            urls = data.get("urls") or []

            # Extract unique hosts and geolocate
            hosts: dict = {}
            for entry in urls[:50]:
                host = entry.get("host", "")
                if host and host not in hosts:
                    # Validate it looks like an IP
                    parts = host.split(".")
                    if len(parts) == 4 and all(p.isdigit() for p in parts):
                        hosts[host] = entry

            if hosts:
                geo_map = await _batch_geolocate(client, list(hosts.keys())[:50])
                for ip, entry in hosts.items():
                    loc = geo_map.get(ip)
                    if loc:
                        threat_type = entry.get("threat", "malware")
                        results.append({
                            "title": f"Malware Host: {ip} ({threat_type})",
                            "indicator": ip,
                            "indicator_type": "IPv4",
                            "severity": "high" if threat_type in ("malware_download", "ransomware") else "medium",
                            "source": "URLhaus (abuse.ch)",
                            "latitude": loc[0],
                            "longitude": loc[1],
                            "country": loc[2],
                            "tags": threat_type,
                        })

        except Exception as exc:
            logger.debug("URLhaus fetch failed: %s", exc)

        return results


    # ------------------------------------------------------------------
    # DShield / SANS Internet Storm Center — top attacking IPs
    # ------------------------------------------------------------------
    async def _from_dshield(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch top attacking IPs from SANS ISC DShield (free, no key)."""
        results: List[dict] = []
        try:
            resp = await client.get(
                "https://isc.sans.edu/api/topips/records/30?json",
                timeout=httpx.Timeout(connect=10.0, read=20.0, write=5.0, pool=10.0),
                headers={
                    "User-Agent": "AgusOSINT/2.0 (threat-intel; contact@agus.dev)",
                    "Accept": "application/json",
                },
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            ips = []
            for entry in data:
                src = entry.get("source") or entry.get("ipaddr", "")
                if src and "." in src:
                    ips.append((src, entry))

            if ips:
                geo_map = await _batch_geolocate(client, [ip for ip, _ in ips[:30]])
                for ip, entry in ips[:30]:
                    loc = geo_map.get(ip)
                    if loc:
                        count = int(entry.get("count", 0) or entry.get("reports", 0) or 0)
                        severity = "critical" if count > 10000 else "high" if count > 1000 else "medium"
                        results.append({
                            "title": f"DShield Top Attacker: {ip} ({count} reports)",
                            "indicator": ip,
                            "indicator_type": "IPv4",
                            "severity": severity,
                            "source": "SANS ISC DShield",
                            "latitude": loc[0],
                            "longitude": loc[1],
                            "country": loc[2],
                            "tags": f"attacks:{count}",
                        })
        except Exception as exc:
            logger.debug("DShield fetch failed: %s", exc)
        return results

    # ------------------------------------------------------------------
    # Feodo Tracker (abuse.ch) — botnet C2 infrastructure
    # ------------------------------------------------------------------
    async def _from_feodo_tracker(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch active botnet C2 servers from Feodo Tracker (free, CC0)."""
        results: List[dict] = []
        try:
            resp = await client.get(
                "https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.json",
                timeout=httpx.Timeout(connect=10.0, read=20.0, write=5.0, pool=10.0),
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            ips = []
            for entry in data[:50]:
                ip = entry.get("ip_address", "")
                if ip:
                    ips.append((ip, entry))

            if ips:
                geo_map = await _batch_geolocate(client, [ip for ip, _ in ips[:50]])
                for ip, entry in ips[:50]:
                    loc = geo_map.get(ip)
                    if loc:
                        malware = entry.get("malware", "Unknown")
                        status = entry.get("status", "")
                        results.append({
                            "title": f"Botnet C2: {ip} ({malware})",
                            "indicator": ip,
                            "indicator_type": "IPv4",
                            "severity": "critical" if status == "online" else "high",
                            "source": "Feodo Tracker (abuse.ch)",
                            "latitude": loc[0],
                            "longitude": loc[1],
                            "country": loc[2],
                            "tags": f"{malware},{entry.get('first_seen', '')}",
                        })
        except Exception as exc:
            logger.debug("Feodo Tracker fetch failed: %s", exc)
        return results

    # ------------------------------------------------------------------
    # CISA KEV — Known Exploited Vulnerabilities
    # ------------------------------------------------------------------
    async def _from_cisa_kev(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch CISA Known Exploited Vulnerabilities catalog (free, no key)."""
        results: List[dict] = []
        try:
            resp = await client.get(
                "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
                timeout=httpx.Timeout(connect=10.0, read=20.0, write=5.0, pool=10.0),
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            vulns = data.get("vulnerabilities") or []
            # Get recent CVEs (last 20 added)
            recent = sorted(vulns, key=lambda v: v.get("dateAdded", ""), reverse=True)[:20]

            # Place at Washington DC (CISA HQ) with slight offsets
            for i, vuln in enumerate(recent):
                cve_id = vuln.get("cveID", "")
                vendor = vuln.get("vendorProject", "")
                product = vuln.get("product", "")
                desc = vuln.get("shortDescription", "")
                # Spread markers around DC area
                lat = 38.9 + (i % 5) * 0.3
                lon = -77.0 + (i // 5) * 0.4
                results.append({
                    "title": f"CISA KEV: {cve_id} — {vendor} {product}",
                    "indicator": cve_id,
                    "indicator_type": "CVE",
                    "severity": "critical",
                    "source": "CISA KEV",
                    "latitude": lat,
                    "longitude": lon,
                    "country": "United States",
                    "tags": f"{vendor},{product}",
                    "description": desc[:200],
                })
        except Exception as exc:
            logger.debug("CISA KEV fetch failed: %s", exc)
        return results


def _pulse_severity(pulse: dict) -> str:
    """Estimate severity from OTX pulse metadata."""
    tags = " ".join(pulse.get("tags") or []).lower()
    adversary = (pulse.get("adversary") or "").lower()
    if any(w in tags for w in ("apt", "ransomware", "critical", "zero-day", "0day")):
        return "critical"
    if any(w in adversary for w in ("apt", "lazarus", "fancy bear", "cozy bear")):
        return "critical"
    if any(w in tags for w in ("malware", "exploit", "backdoor", "trojan", "rat")):
        return "high"
    if any(w in tags for w in ("phishing", "spam", "suspicious", "scanner")):
        return "medium"
    return "low"


async def _batch_geolocate(client: httpx.AsyncClient, ips: list) -> dict:
    """Batch geolocate IPs using ip-api.com (free, 100/min, supports batch)."""
    geo: dict = {}
    # ip-api.com batch endpoint accepts up to 100 IPs
    for i in range(0, len(ips), 100):
        batch = [{"query": ip} for ip in ips[i:i + 100]]
        try:
            resp = await client.post(
                "http://ip-api.com/batch?fields=query,lat,lon,country,city,isp,status",
                json=batch,
                timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
            )
            resp.raise_for_status()
            for item in resp.json():
                if item.get("status") == "success":
                    geo[item["query"]] = (
                        item["lat"], item["lon"],
                        item.get("country", ""),
                    )
        except Exception as exc:
            logger.warning("ip-api batch geolocate failed: %s", exc)
        if i + 100 < len(ips):
            await asyncio.sleep(1.0)  # Rate limit: 100/min
    return geo
