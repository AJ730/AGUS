"""Aircraft carrier and major warship fetcher.

Sources:
  1. Wikidata SPARQL — active fleet home ports
  2. Google News RSS — deployment headlines
  3. GDELT DOC API — deployment headlines (fallback)
  4. Defense RSS feeds — USNI News, Naval News
  5. ADS-B military — carrier-based aircraft inference

Headlines from all news sources are correlated: carrier name + region
mentions across multiple independent sources increase confidence.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

# ── Wikidata: active carrier home ports ──────────────────────────────
_SPARQL = """
SELECT DISTINCT ?ship ?shipLabel ?classLabel ?operatorLabel ?portLabel ?lat ?lon WHERE {
  VALUES ?type { wd:Q17205 wd:Q2526255 wd:Q743004 wd:Q1792159 }
  ?ship wdt:P31 ?type .
  FILTER NOT EXISTS { ?ship wdt:P793 wd:Q52706 . }
  FILTER NOT EXISTS { ?ship wdt:P793 wd:Q18812508 . }
  FILTER NOT EXISTS { ?ship wdt:P793 wd:Q15052537 . }
  OPTIONAL { ?ship wdt:P729 ?commissioned . }
  FILTER(!BOUND(?commissioned) || YEAR(?commissioned) >= 1970)
  { ?ship wdt:P504 ?port . ?port wdt:P625 ?coord . }
  UNION
  { ?ship wdt:P625 ?coord . }
  OPTIONAL { ?ship wdt:P289 ?class . }
  OPTIONAL { ?ship wdt:P137 ?operator . }
  BIND(geof:latitude(?coord) AS ?lat)
  BIND(geof:longitude(?coord) AS ?lon)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 300
"""

_DEFUNCT_NAVIES = frozenset([
    "imperial japanese navy", "kriegsmarine", "imperial german navy",
    "regia marina", "royal italian navy", "imperial russian navy",
    "soviet navy", "ottoman navy", "austro-hungarian navy",
    "confederate states navy", "free french naval forces",
])

# ── Carrier names for headline matching ──────────────────────────────
_US_CARRIERS = [
    "Gerald R. Ford", "Ford", "Nimitz", "Eisenhower", "Ike",
    "Carl Vinson", "Vinson", "Theodore Roosevelt", "Roosevelt",
    "Abraham Lincoln", "Lincoln", "George Washington",
    "John C. Stennis", "Stennis", "Harry S. Truman", "Truman",
    "Ronald Reagan", "Reagan", "George H.W. Bush",
]

_OTHER_CARRIERS = [
    ("Charles de Gaulle", "French Navy"),
    ("Queen Elizabeth", "Royal Navy"),
    ("Prince of Wales", "Royal Navy"),
    ("Liaoning", "People's Liberation Army Navy"),
    ("Shandong", "People's Liberation Army Navy"),
    ("Fujian", "People's Liberation Army Navy"),
    ("Admiral Kuznetsov", "Russian Navy"),
    ("Vikrant", "Indian Navy"),
    ("Vikramaditya", "Indian Navy"),
    ("Cavour", "Italian Navy"),
    ("Juan Carlos", "Spanish Navy"),
    ("Izumo", "Japan Maritime Self-Defense Force"),
    ("Kaga", "Japan Maritime Self-Defense Force"),
]

# ── Region keywords → approximate deployment coordinates ─────────────
_DEPLOYMENT_REGIONS: Dict[str, Tuple[float, float]] = {
    "middle east":      (25.0, 56.0),
    "persian gulf":     (26.5, 52.0),
    "arabian gulf":     (26.5, 52.0),
    "arabian sea":      (18.0, 63.0),
    "gulf of oman":     (24.5, 59.0),
    "strait of hormuz": (26.5, 56.5),
    "red sea":          (20.0, 38.5),
    "bab el-mandeb":    (12.5, 43.3),
    "gulf of aden":     (12.0, 46.0),
    "mediterranean":    (35.0, 20.0),
    "eastern mediterranean": (34.5, 32.0),
    "south china sea":  (12.0, 114.0),
    "taiwan strait":    (24.0, 119.5),
    "east china sea":   (30.0, 126.0),
    "western pacific":  (20.0, 140.0),
    "pacific":          (25.0, 170.0),
    "indo-pacific":     (10.0, 120.0),
    "atlantic":         (35.0, -45.0),
    "north atlantic":   (50.0, -30.0),
    "baltic":           (57.0, 19.0),
    "black sea":        (43.5, 34.0),
    "indian ocean":     (-5.0, 72.0),
    "horn of africa":   (10.0, 50.0),
    "yemen":            (15.0, 48.0),
    "houthi":           (15.0, 44.0),
    "iran":             (27.0, 55.0),
    "syria":            (35.5, 36.0),
    "libya":            (32.5, 15.0),
    "korea":            (36.0, 128.0),
    "japan":            (34.0, 137.0),
    "south korea":      (35.5, 129.0),
    "guam":             (13.5, 144.8),
    "hawaii":           (21.3, -157.8),
    "norfolk":          (36.9, -76.3),
    "san diego":        (32.7, -117.2),
    "philippine sea":   (18.0, 130.0),
    "suez canal":       (30.5, 32.3),
}

# ── Google News RSS search URLs ──────────────────────────────────────
_GNEWS_QUERIES = [
    "aircraft+carrier+deployment",
    "carrier+strike+group+deployed",
    "USS+carrier+navy+gulf",
    "navy+carrier+strait",
]

# ── Defense RSS feeds ────────────────────────────────────────────────
_DEFENSE_FEEDS = [
    "https://news.usni.org/category/fleet-tracker/feed",
    "https://www.navalnews.com/feed/",
]


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
    """Extract a carrier name and operator from a headline."""
    title_lower = title.lower()
    # Check non-US carriers first (more specific names)
    for name, navy in _OTHER_CARRIERS:
        if name.lower() in title_lower:
            return name, navy
    # US carriers
    for name in _US_CARRIERS:
        if name.lower() in title_lower:
            full = f"USS {name}" if not name.startswith("USS") else name
            return full, "United States Navy"
    # Generic
    if "aircraft carrier" in title_lower or "carrier strike" in title_lower:
        return "Aircraft Carrier", ""
    return "", ""


def _parse_rss_titles(xml_text: str) -> List[str]:
    """Extract <title> text from RSS XML."""
    titles = []
    try:
        root = ET.fromstring(xml_text)
        # Standard RSS 2.0: channel/item/title
        for item in root.iter("item"):
            t = item.find("title")
            if t is not None and t.text:
                titles.append(t.text.strip())
        # Atom: entry/title
        if not titles:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                t = entry.find("atom:title", ns) or entry.find("title")
                if t is not None and t.text:
                    titles.append(t.text.strip())
    except ET.ParseError:
        pass
    return titles


class CarrierFetcher(BaseFetcher):
    """Fetches carrier locations from Wikidata + multi-source news correlation."""

    async def _from_wikidata(self, client: httpx.AsyncClient) -> List[dict]:
        bindings = await self._wikidata(client, _SPARQL)
        results, seen = [], set()
        for b in bindings:
            coords = self._coords(b)
            if not coords:
                continue
            operator = self._label(b, "operatorLabel")
            if operator.lower() in _DEFUNCT_NAVIES:
                continue
            key = f"{round(coords[0], 2)}:{round(coords[1], 2)}"
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "name": self._label(b, "shipLabel", "Warship"),
                "class": self._label(b, "classLabel"),
                "operator": operator,
                "home_port": self._label(b, "portLabel"),
                "latitude": coords[0], "longitude": coords[1],
                "type": "carrier", "status": "home port",
            })
        return results

    async def _headlines_from_google_news(self) -> List[Tuple[str, str]]:
        """Fetch carrier headlines from Google News RSS. Returns (title, source)."""
        headlines: List[Tuple[str, str]] = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
            for q in _GNEWS_QUERIES:
                try:
                    resp = await c.get(
                        f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en",
                    )
                    if resp.status_code != 200:
                        continue
                    titles = _parse_rss_titles(resp.text)
                    for t in titles:
                        headlines.append((t, "Google News"))
                except Exception as exc:
                    logger.debug("Carrier Google News '%s': %s", q[:20], exc)
        logger.info("Carrier Google News: %d headlines", len(headlines))
        return headlines

    async def _headlines_from_defense_rss(self) -> List[Tuple[str, str]]:
        """Fetch carrier headlines from defense RSS feeds. Returns (title, source)."""
        headlines: List[Tuple[str, str]] = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
            for feed_url in _DEFENSE_FEEDS:
                try:
                    resp = await c.get(feed_url)
                    if resp.status_code != 200:
                        continue
                    titles = _parse_rss_titles(resp.text)
                    source = "USNI" if "usni" in feed_url else "Naval News"
                    for t in titles:
                        headlines.append((t, source))
                except Exception as exc:
                    logger.debug("Carrier RSS %s: %s", feed_url.split("/")[2], exc)
        logger.info("Carrier Defense RSS: %d headlines", len(headlines))
        return headlines

    async def _headlines_from_gdelt(self, client: httpx.AsyncClient) -> List[Tuple[str, str]]:
        """Fetch carrier headlines from GDELT DOC API. Returns (title, source)."""
        headlines: List[Tuple[str, str]] = []
        queries = [
            '"aircraft carrier" OR "carrier strike group"',
            '"USS Ford" OR "USS Nimitz" OR "USS Eisenhower"',
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
                        "TIMESPAN": "30D",
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
        """Correlate headlines from multiple sources into deployment records.

        Tracks which independent sources confirm each carrier+region combo.
        More sources = higher confidence.
        """
        # region_key → {carrier, region, lat, lon, sources, headlines}
        deployments: Dict[str, dict] = {}

        for title, source in all_headlines:
            deployment = _extract_deployment(title)
            if not deployment:
                continue
            region, lat, lon = deployment
            carrier_name, operator = _extract_carrier_name(title)
            if not carrier_name:
                continue

            key = f"{round(lat, 0)}:{round(lon, 0)}"

            if key not in deployments:
                deployments[key] = {
                    "carrier": carrier_name,
                    "operator": operator or "Unknown",
                    "region": region,
                    "lat": lat, "lon": lon,
                    "sources": set(),
                    "headlines": [],
                    "specificity": 0,
                }
            d = deployments[key]
            d["sources"].add(source)
            d["headlines"].append(title[:120])
            # Prefer the most specific carrier name
            if carrier_name != "Aircraft Carrier" and d["carrier"] == "Aircraft Carrier":
                d["carrier"] = carrier_name
                d["operator"] = operator or d["operator"]
            if carrier_name != "Aircraft Carrier":
                d["specificity"] += 1

        results = []
        for key, d in deployments.items():
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
            })

        if results:
            logger.info(
                "Carrier correlation: %d deployments (%s)",
                len(results),
                ", ".join(f"{r['name']}@{r['status']}" for r in results),
            )
        return results

    async def _from_news_correlation(self, client: httpx.AsyncClient) -> List[dict]:
        """Gather headlines from all news sources and correlate."""
        all_headlines: List[Tuple[str, str]] = []

        # Fetch from all sources (independent, could parallelize)
        for fetch_fn in [
            self._headlines_from_google_news,
            self._headlines_from_defense_rss,
        ]:
            try:
                all_headlines.extend(await fetch_fn())
            except Exception as exc:
                logger.debug("Carrier headlines: %s", exc)

        # GDELT needs the shared client
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

        # E-2 Hawkeye and CMV-22 Osprey are carrier-only aircraft
        carrier_types = {"E2", "C2", "V22"}
        carrier_ac = [
            a for a in ac_list
            if (a.get("t") or "").upper() in carrier_types
            and a.get("lat") is not None
            and a.get("lon") is not None
        ]
        if not carrier_ac:
            return []

        results = []
        for a in carrier_ac:
            lat, lon = a["lat"], a["lon"]
            results.append({
                "name": f"Carrier (detected via {a.get('t', '?')} {a.get('flight', '').strip()})",
                "class": "Inferred from ADS-B",
                "operator": "United States Navy",
                "home_port": "",
                "latitude": lat, "longitude": lon,
                "type": "carrier", "status": "detected",
                "source": "ADS-B",
            })
        logger.info("Carrier ADS-B: %d carrier aircraft detected", len(results))
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        all_results: List[dict] = []

        # Source 1: Wikidata (active fleet home ports)
        try:
            all_results.extend(await self._from_wikidata(client))
        except Exception as exc:
            logger.warning("Carriers wikidata: %s", exc)

        # Source 2: Multi-source news correlation (Google News + Defense RSS + GDELT)
        try:
            all_results.extend(await self._from_news_correlation(client))
        except Exception as exc:
            logger.warning("Carriers news: %s", exc)

        # Source 3: ADS-B military aircraft inference
        try:
            all_results.extend(await self._from_adsb_mil(client))
        except Exception as exc:
            logger.warning("Carriers ADS-B: %s", exc)

        # Deduplicate by proximity
        seen, unique = set(), []
        for r in all_results:
            key = f"{round(r['latitude'], 1)}:{round(r['longitude'], 1)}"
            if key not in seen:
                seen.add(key)
                unique.append(r)

        logger.info("Carriers total: %d", len(unique))
        return unique
