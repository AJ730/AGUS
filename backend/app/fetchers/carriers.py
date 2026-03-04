"""Aircraft carrier and major warship fetcher — LIVE DATA ONLY.

Sources (priority order — highest wins per carrier):
  1. ADS-B military — carrier-based aircraft inference (real-time)
  2. News correlation — Google News + USNI + Naval News + GDELT (deployed region)

NO Wikidata / home ports — only live-detected positions.
Each carrier appears ONCE (deduplicated by canonical name).
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

# ── Canonical carrier names for matching ──────────────────────────────
# Map short name → (full display name, operator)
_CARRIER_ALIASES: Dict[str, Tuple[str, str]] = {}

_US_CARRIERS_FULL = [
    ("Gerald R. Ford", ["Gerald R. Ford", "Ford"]),
    ("USS Nimitz", ["Nimitz"]),
    ("USS Dwight D. Eisenhower", ["Eisenhower", "Ike"]),
    ("USS Carl Vinson", ["Carl Vinson", "Vinson"]),
    ("USS Theodore Roosevelt", ["Theodore Roosevelt"]),
    ("USS Abraham Lincoln", ["Abraham Lincoln", "Lincoln"]),
    ("USS George Washington", ["George Washington"]),
    ("USS John C. Stennis", ["John C. Stennis", "Stennis"]),
    ("USS Harry S. Truman", ["Harry S. Truman", "Truman"]),
    ("USS Ronald Reagan", ["Ronald Reagan", "Reagan"]),
    ("USS George H.W. Bush", ["George H.W. Bush"]),
]
for _full, _aliases in _US_CARRIERS_FULL:
    for _a in _aliases:
        _CARRIER_ALIASES[_a.lower()] = (_full, "United States Navy")

_OTHER_CARRIERS = [
    ("Charles de Gaulle", "French Navy"),
    ("Queen Elizabeth", "Royal Navy"),
    ("Prince of Wales", "Royal Navy"),
    ("Liaoning", "People's Liberation Army Navy"),
    ("Shandong", "People's Liberation Army Navy"),
    ("Fujian", "People's Liberation Army Navy"),
    ("Admiral Kuznetsov", "Russian Navy"),
    ("INS Vikrant", "Indian Navy"),
    ("INS Vikramaditya", "Indian Navy"),
    ("Cavour", "Italian Navy"),
    ("Juan Carlos I", "Spanish Navy"),
    ("JS Izumo", "Japan Maritime Self-Defense Force"),
    ("JS Kaga", "Japan Maritime Self-Defense Force"),
]
for _name, _navy in _OTHER_CARRIERS:
    _CARRIER_ALIASES[_name.lower()] = (_name, _navy)
    # Also register without prefix
    for prefix in ("INS ", "JS ", "HMS "):
        if _name.startswith(prefix):
            _CARRIER_ALIASES[_name[len(prefix):].lower()] = (_name, _navy)

# ── Region keywords → AT-SEA coordinates (never on land) ─────────────
_DEPLOYMENT_REGIONS: Dict[str, Tuple[float, float]] = {
    "middle east":      (25.0, 54.0),     # Persian Gulf open water
    "persian gulf":     (26.0, 52.0),     # Central Persian Gulf
    "arabian gulf":     (26.0, 52.0),
    "arabian sea":      (16.0, 63.0),     # Open Arabian Sea
    "gulf of oman":     (24.5, 59.5),     # Gulf of Oman center
    "strait of hormuz": (26.3, 56.8),     # Hormuz channel
    "red sea":          (19.0, 38.5),     # Central Red Sea
    "bab el-mandeb":    (12.6, 43.5),     # Bab el-Mandeb strait
    "gulf of aden":     (12.5, 47.0),     # Gulf of Aden center
    "mediterranean":    (35.5, 18.0),     # Central Mediterranean
    "eastern mediterranean": (34.0, 30.0),# Off Cyprus coast
    "south china sea":  (14.0, 115.0),    # Central SCS
    "taiwan strait":    (24.5, 119.0),    # Mid-strait water
    "east china sea":   (29.0, 126.0),    # Open ECS
    "western pacific":  (20.0, 140.0),    # Open Pacific
    "pacific":          (22.0, -165.0),   # Central Pacific
    "indo-pacific":     (8.0, 118.0),     # Open water
    "atlantic":         (32.0, -45.0),    # Mid-Atlantic
    "north atlantic":   (48.0, -25.0),    # North Atlantic
    "baltic":           (56.5, 18.0),     # Central Baltic Sea
    "black sea":        (43.0, 33.0),     # Central Black Sea
    "indian ocean":     (-8.0, 72.0),     # Central Indian Ocean
    "horn of africa":   (11.0, 51.0),     # Off Somalia coast
    "yemen":            (14.0, 49.0),     # Off Yemen coast (sea)
    "houthi":           (14.5, 43.5),     # Southern Red Sea
    "iran":             (26.0, 55.0),     # Off Iranian coast (sea)
    "syria":            (35.0, 34.0),     # Off Syrian coast (sea)
    "libya":            (33.5, 14.0),     # Off Libyan coast (sea)
    "korea":            (35.0, 130.0),    # Sea of Japan / Korea Strait
    "japan":            (33.0, 137.0),    # Off Japan (Pacific side)
    "south korea":      (34.5, 129.5),    # Korea Strait
    "guam":             (13.0, 145.5),    # Off Guam (open sea)
    "hawaii":           (20.5, -158.5),   # Off Hawaii (open sea)
    "norfolk":          (36.5, -74.5),    # Off Norfolk (Atlantic)
    "san diego":        (32.5, -118.0),   # Off San Diego coast (sea)
    "philippine sea":   (18.0, 132.0),    # Open Philippine Sea
    "suez canal":       (30.5, 32.6),     # Suez Canal waterway
}

# ── Google News RSS search URLs ──────────────────────────────────────
_GNEWS_QUERIES = [
    "aircraft+carrier+deployment",
    "carrier+strike+group+deployed",
    "USS+carrier+navy+gulf+OR+pacific+OR+mediterranean",
    "navy+carrier+strait+OR+sea+OR+ocean",
    "carrier+strike+group+arrives+OR+transits+OR+enters",
    "USS+Ford+OR+Nimitz+OR+Eisenhower+OR+Lincoln+OR+Vinson+OR+Reagan",
    "HMS+Queen+Elizabeth+OR+Prince+of+Wales+carrier",
    "Charles+de+Gaulle+carrier+OR+Liaoning+OR+Shandong",
]

# ── Defense & Naval RSS feeds ────────────────────────────────────────
_DEFENSE_FEEDS = [
    "https://news.usni.org/category/fleet-tracker/feed",
    "https://www.navalnews.com/feed/",
    "https://www.defensenews.com/arc/outboundfeeds/rss/category/naval/?outputType=xml",
    "https://news.usni.org/feed",
    "https://www.maritime-executive.com/feed",
]

# Priority: higher number wins when deduplicating
_PRIORITY = {"news": 1, "adsb": 2}


def _extract_deployment(title: str) -> Optional[Tuple[str, float, float]]:
    """Extract a deployment region and coords from a news headline."""
    title_lower = title.lower()
    for region, (lat, lon) in sorted(
        _DEPLOYMENT_REGIONS.items(), key=lambda x: -len(x[0])
    ):
        if region in title_lower:
            return region.title(), lat, lon
    return None


def _extract_carrier_name(title: str) -> Tuple[str, str]:
    """Extract a canonical carrier name and operator from a headline."""
    title_lower = title.lower()
    # Check all known carrier names (longest first to avoid partial matches)
    for alias in sorted(_CARRIER_ALIASES.keys(), key=len, reverse=True):
        if alias in title_lower:
            return _CARRIER_ALIASES[alias]
    # Generic — only if explicitly about carriers
    if "aircraft carrier" in title_lower or "carrier strike" in title_lower:
        return "Aircraft Carrier", ""
    return "", ""


def _normalize_carrier_name(name: str) -> str:
    """Normalize a carrier name to a canonical key for deduplication."""
    lower = name.lower().strip()
    # Check alias table
    for alias, (full, _) in _CARRIER_ALIASES.items():
        if alias in lower or lower in alias:
            return full
    # Strip common prefixes for comparison
    for prefix in ("uss ", "hms ", "ins ", "js ", "fs "):
        if lower.startswith(prefix):
            lower = lower[len(prefix):]
    return lower


def _parse_rss_titles(xml_text: str) -> List[str]:
    """Extract <title> text from RSS XML."""
    titles = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.iter("item"):
            t = item.find("title")
            if t is not None and t.text:
                titles.append(t.text.strip())
        if not titles:
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                t = entry.find("{http://www.w3.org/2005/Atom}title") or entry.find("title")
                if t is not None and t.text:
                    titles.append(t.text.strip())
    except ET.ParseError:
        pass
    return titles


class CarrierFetcher(BaseFetcher):
    """Fetches carrier locations with live-position priority."""

    async def _headlines_from_google_news(self) -> List[Tuple[str, str]]:
        headlines: List[Tuple[str, str]] = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
            for q in _GNEWS_QUERIES:
                try:
                    resp = await c.get(
                        f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en",
                    )
                    if resp.status_code != 200:
                        continue
                    for t in _parse_rss_titles(resp.text):
                        headlines.append((t, "Google News"))
                except Exception as exc:
                    logger.debug("Carrier Google News '%s': %s", q[:20], exc)
        logger.info("Carrier Google News: %d headlines", len(headlines))
        return headlines

    async def _headlines_from_defense_rss(self) -> List[Tuple[str, str]]:
        headlines: List[Tuple[str, str]] = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
            for feed_url in _DEFENSE_FEEDS:
                try:
                    resp = await c.get(feed_url)
                    if resp.status_code != 200:
                        continue
                    source = "USNI" if "usni" in feed_url else "Naval News"
                    for t in _parse_rss_titles(resp.text):
                        headlines.append((t, source))
                except Exception as exc:
                    logger.debug("Carrier RSS %s: %s", feed_url.split("/")[2], exc)
        logger.info("Carrier Defense RSS: %d headlines", len(headlines))
        return headlines

    async def _headlines_from_gdelt(self, client: httpx.AsyncClient) -> List[Tuple[str, str]]:
        headlines: List[Tuple[str, str]] = []
        queries = [
            '"aircraft carrier" OR "carrier strike group"',
            '"USS Ford" OR "USS Nimitz" OR "USS Eisenhower" OR "USS Lincoln" OR "USS Vinson"',
        ]
        for q in queries:
            try:
                resp = await client.get(
                    "https://api.gdeltproject.org/api/v2/doc/doc",
                    params={
                        "query": f"{q} sourcelang:english",
                        "mode": "ArtList",
                        "maxrecords": "50",
                        "format": "json",
                        "TIMESPAN": "14D",
                    },
                    timeout=20.0,
                )
                if resp.status_code != 200:
                    continue
                text = resp.text.strip()
                if not text or not text.startswith("{"):
                    continue
                for art in resp.json().get("articles") or []:
                    title = art.get("title", "")
                    if title:
                        headlines.append((title, "GDELT"))
            except Exception as exc:
                logger.debug("Carrier GDELT: %s", exc)
        if headlines:
            logger.info("Carrier GDELT: %d headlines", len(headlines))
        return headlines

    def _correlate_headlines(
        self, all_headlines: List[Tuple[str, str]]
    ) -> List[dict]:
        """Correlate headlines into deployment records, deduped by carrier name."""
        # carrier_canonical → best deployment info
        deployments: Dict[str, dict] = {}

        for title, source in all_headlines:
            deployment = _extract_deployment(title)
            if not deployment:
                continue
            region, lat, lon = deployment
            carrier_name, operator = _extract_carrier_name(title)
            if not carrier_name or carrier_name == "Aircraft Carrier":
                continue

            canon = _normalize_carrier_name(carrier_name)
            if canon not in deployments:
                deployments[canon] = {
                    "carrier": carrier_name,
                    "operator": operator or "Unknown",
                    "region": region,
                    "lat": lat, "lon": lon,
                    "sources": set(),
                    "headlines": [],
                }
            d = deployments[canon]
            d["sources"].add(source)
            d["headlines"].append(title[:120])

        results = []
        for canon, d in deployments.items():
            n_sources = len(d["sources"])
            confidence = "high" if n_sources >= 3 else "medium" if n_sources >= 2 else "low"
            results.append({
                "name": d["carrier"],
                "class": "Carrier Strike Group",
                "operator": d["operator"],
                "home_port": "",
                "latitude": d["lat"], "longitude": d["lon"],
                "type": "carrier",
                "status": f"deployed - {d['region']}",
                "source": ", ".join(sorted(d["sources"])),
                "confidence": confidence,
                "corroborating_sources": n_sources,
                "headline": d["headlines"][0] if d["headlines"] else "",
                "_source_priority": _PRIORITY["news"],
            })

        if results:
            logger.info(
                "Carrier correlation: %d deployments (%s)",
                len(results),
                ", ".join(f"{r['name']}@{r['status']}" for r in results),
            )
        return results

    async def _from_news_correlation(self, client: httpx.AsyncClient) -> List[dict]:
        all_headlines: List[Tuple[str, str]] = []
        for fetch_fn in [
            self._headlines_from_google_news,
            self._headlines_from_defense_rss,
        ]:
            try:
                all_headlines.extend(await fetch_fn())
            except Exception as exc:
                logger.debug("Carrier headlines: %s", exc)
        try:
            all_headlines.extend(await self._headlines_from_gdelt(client))
        except Exception as exc:
            logger.debug("Carrier GDELT headlines: %s", exc)

        logger.info("Carrier total headlines: %d from news sources", len(all_headlines))
        return self._correlate_headlines(all_headlines)

    async def _from_adsb_mil(self, client: httpx.AsyncClient) -> List[dict]:
        """Detect carrier positions from carrier-based military aircraft."""
        try:
            resp = await client.get("https://api.adsb.lol/v2/mil", timeout=15)
            resp.raise_for_status()
            ac_list = resp.json().get("ac", [])
        except Exception as exc:
            logger.debug("Carrier ADS-B mil: %s", exc)
            return []

        # E-2 Hawkeye, C-2 Greyhound, CMV-22 Osprey are carrier-only aircraft
        carrier_types = {"E2", "C2", "V22"}
        carrier_ac = [
            a for a in ac_list
            if (a.get("t") or "").upper() in carrier_types
            and a.get("lat") is not None
            and a.get("lon") is not None
        ]
        if not carrier_ac:
            return []

        # Cluster nearby aircraft (within ~200km) to avoid multiple pins
        clusters: List[dict] = []
        for a in carrier_ac:
            lat, lon = a["lat"], a["lon"]
            merged = False
            for c in clusters:
                if abs(c["lat"] - lat) < 2 and abs(c["lon"] - lon) < 2:
                    c["aircraft"].append(a)
                    c["lat"] = (c["lat"] + lat) / 2
                    c["lon"] = (c["lon"] + lon) / 2
                    merged = True
                    break
            if not merged:
                clusters.append({"lat": lat, "lon": lon, "aircraft": [a]})

        results = []
        for c in clusters:
            types = ", ".join(set(a.get("t", "?") for a in c["aircraft"]))
            flights = ", ".join(
                a.get("flight", "").strip() for a in c["aircraft"]
                if a.get("flight", "").strip()
            )
            results.append({
                "name": f"Carrier (ADS-B: {types})",
                "class": f"Detected via {len(c['aircraft'])} aircraft: {flights}" if flights else "Inferred from ADS-B",
                "operator": "United States Navy",
                "home_port": "",
                "latitude": c["lat"], "longitude": c["lon"],
                "type": "carrier", "status": "detected - live",
                "source": "ADS-B",
                "confidence": "high" if len(c["aircraft"]) >= 2 else "medium",
                "_source_priority": _PRIORITY["adsb"],
            })
        logger.info("Carrier ADS-B: %d carrier positions from %d aircraft",
                     len(results), len(carrier_ac))
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        all_results: List[dict] = []

        # Gather from live sources only (no Wikidata home ports)
        for label, fetch_fn in [
            ("news", lambda: self._from_news_correlation(client)),
            ("adsb", lambda: self._from_adsb_mil(client)),
        ]:
            try:
                all_results.extend(await fetch_fn())
            except Exception as exc:
                logger.warning("Carriers %s: %s", label, exc)

        # Deduplicate by carrier name — highest priority source wins.
        # This means if we know a carrier is deployed via news or ADS-B,
        # we show THAT location instead of the Wikidata home port.
        best: Dict[str, dict] = {}
        for r in all_results:
            canon = _normalize_carrier_name(r["name"])
            priority = r.pop("_source_priority", -1)
            existing = best.get(canon)
            if existing is None or priority > existing["_pri"]:
                best[canon] = {**r, "_pri": priority}

        unique = []
        for canon, r in best.items():
            r.pop("_pri", None)
            unique.append(r)

        logger.info("Carriers total: %d unique", len(unique))
        return unique
