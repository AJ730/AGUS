"""Israeli rocket alert fetcher — live alert data from multiple sources."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import httpx

from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

# Multiple alert API endpoints (community mirrors + official)
_ALERT_SOURCES = [
    # Tzeva Adom (Red Alert) community API
    "https://api.tzevaadom.co.il/notifications",
    # HA alerts aggregator
    "https://www.oref.org.il/WarningMessages/alert/alerts.json",
    # History endpoint
    "https://www.oref.org.il/warningMessages/alert/History/AlertsHistory.json",
]

# OREF-specific headers
_OREF_HEADERS = {
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
}

# Known Israeli cities/areas with coordinates for geocoding alerts
_ISRAEL_LOCATIONS: Dict[str, Tuple[float, float]] = {
    # Major cities
    "tel aviv": (32.0853, 34.7818), "jerusalem": (31.7683, 35.2137),
    "haifa": (32.7940, 34.9896), "beer sheva": (31.2518, 34.7913),
    "be'er sheva": (31.2518, 34.7913), "ashkelon": (31.6688, 34.5743),
    "ashdod": (31.8044, 34.6553), "sderot": (31.5249, 34.5960),
    "netivot": (31.4206, 34.5890), "ofakim": (31.3168, 34.6177),
    "rishon lezion": (31.9730, 34.7925), "petah tikva": (32.0879, 34.8875),
    "netanya": (32.3215, 34.8532), "herzliya": (32.1627, 34.8443),
    "ramat gan": (32.0686, 34.8249), "holon": (32.0105, 34.7751),
    "bat yam": (32.0230, 34.7503), "eilat": (29.5577, 34.9519),
    "tiberias": (32.7922, 35.5312), "nahariya": (33.0074, 35.0950),
    "kiryat shmona": (33.2079, 35.5710), "metula": (33.2797, 35.5793),
    "safed": (32.9646, 35.4968), "acre": (32.9273, 35.0768),
    "nazareth": (32.7019, 35.3038), "karmiel": (32.9196, 35.3043),
    "dimona": (31.0702, 35.0293), "arad": (31.2567, 35.2130),
    # Southern / Gaza envelope
    "re'im": (31.3755, 34.4019), "nir oz": (31.2873, 34.3954),
    "be'eri": (31.3486, 34.4893), "kfar aza": (31.3812, 34.4516),
    "nahal oz": (31.3932, 34.4629), "kissufim": (31.3300, 34.3975),
    "zikim": (31.5553, 34.5073), "yad mordechai": (31.5806, 34.5547),
    # Northern border
    "avivim": (33.0808, 35.5043), "shlomi": (33.0793, 35.1425),
    "hanita": (33.0897, 35.1581), "manara": (33.2313, 35.5634),
    "misgav am": (33.2327, 35.5569),
    # Golan
    "majdal shams": (33.2724, 35.7694), "katzrin": (32.9923, 35.6915),
}

# Region-level fallback coordinates
_REGION_COORDS: Dict[str, Tuple[float, float]] = {
    "gaza envelope": (31.35, 34.45), "western negev": (31.30, 34.40),
    "negev": (31.00, 34.80), "golan": (33.00, 35.75),
    "upper galilee": (33.05, 35.50), "lower galilee": (32.75, 35.40),
    "galilee panhandle": (33.15, 35.55), "sharon": (32.30, 34.85),
    "shfela": (31.75, 34.85), "dan region": (32.05, 34.80),
    "haifa bay": (32.80, 35.05), "carmel coast": (32.70, 34.95),
    "dead sea": (31.50, 35.40), "arava": (30.50, 35.15),
    "central israel": (32.00, 34.80), "northern israel": (33.00, 35.50),
    "southern israel": (31.25, 34.50),
}


def _geocode_alert(location: str) -> Tuple[float, float] | None:
    """Geocode an alert location name."""
    loc_lower = location.lower().strip()
    for city, coords in _ISRAEL_LOCATIONS.items():
        if city in loc_lower or loc_lower in city:
            return coords
    for region, coords in _REGION_COORDS.items():
        if region in loc_lower or loc_lower in region:
            return coords
    return None


class RocketAlertFetcher(BaseFetcher):
    """Fetches live rocket/missile alerts from Israeli alert systems."""

    async def _from_tzevaadom(self, client: httpx.AsyncClient) -> List[dict]:
        """Try Tzeva Adom community API."""
        results: List[dict] = []
        try:
            resp = await client.get(
                "https://api.tzevaadom.co.il/notifications",
                headers={"Accept": "application/json"},
                timeout=15.0,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            alerts = data if isinstance(data, list) else data.get("alerts", data.get("notifications", []))
            now_iso = datetime.now(timezone.utc).isoformat()
            for alert in alerts[:100]:
                locations = alert.get("cities", alert.get("data", alert.get("locations", "")))
                if isinstance(locations, str):
                    locations = [locations] if locations else []
                elif not isinstance(locations, list):
                    continue
                threat = alert.get("threat", alert.get("cat", "rockets"))
                alert_time = alert.get("time", alert.get("alertDate", now_iso))

                for loc_name in locations:
                    if not isinstance(loc_name, str) or not loc_name.strip():
                        continue
                    coords = _geocode_alert(loc_name)
                    if not coords:
                        continue
                    results.append({
                        "title": f"Alert: {loc_name}",
                        "latitude": coords[0],
                        "longitude": coords[1],
                        "location": loc_name,
                        "alert_type": str(threat),
                        "severity": "critical",
                        "date": str(alert_time),
                        "source": "Tzeva Adom",
                        "type": "rocket_alert",
                    })
        except Exception as exc:
            logger.debug("Tzeva Adom API: %s", exc)
        return results

    async def _from_oref(self, client: httpx.AsyncClient) -> List[dict]:
        """Try official OREF endpoints."""
        results: List[dict] = []
        for url in _ALERT_SOURCES[1:]:
            try:
                resp = await client.get(
                    url, headers=_OREF_HEADERS,
                    timeout=httpx.Timeout(connect=10.0, read=15.0, write=5.0, pool=10.0),
                )
                if resp.status_code != 200:
                    continue
                text = resp.text.strip()
                if not text or text in ("[]", "null"):
                    continue
                if text.startswith("\ufeff"):
                    text = text[1:]

                import json
                alerts = json.loads(text)
                if not isinstance(alerts, list):
                    alerts = [alerts]

                for alert in alerts:
                    locations = []
                    if isinstance(alert.get("data"), list):
                        locations = alert["data"]
                    elif isinstance(alert.get("data"), str):
                        locations = [alert["data"]]

                    alert_title = alert.get("title", "Alert")
                    alert_cat = str(alert.get("cat", "1"))
                    alert_date = alert.get("alertDate", alert.get("date", ""))

                    alert_type = {
                        "1": "rocket_alert", "2": "uav_intrusion",
                        "3": "earthquake", "6": "hostile_aircraft",
                    }.get(alert_cat, "rocket_alert")

                    for loc_name in locations:
                        if not isinstance(loc_name, str):
                            continue
                        coords = _geocode_alert(loc_name)
                        if not coords:
                            continue
                        results.append({
                            "title": f"{alert_title}: {loc_name}",
                            "latitude": coords[0],
                            "longitude": coords[1],
                            "location": loc_name,
                            "alert_type": alert_type,
                            "severity": "critical",
                            "date": alert_date,
                            "source": "OREF",
                            "type": "rocket_alert",
                        })
                if results:
                    break
            except Exception as exc:
                logger.debug("OREF %s: %s", url.split("/")[-1], exc)
        return results

    async def _from_gdelt_alerts(self, client: httpx.AsyncClient) -> List[dict]:
        """Fallback: fetch recent rocket alert news from GDELT."""
        results: List[dict] = []
        try:
            features = await self._gdelt(
                client,
                '("rocket alert" OR "red alert" OR "tzeva adom" OR "iron dome" OR "missile attack" OR "rocket attack") (Israel OR Gaza OR Lebanon OR Hezbollah)',
                "7D", 50,
            )
            for feat in features:
                coords = (feat.get("geometry") or {}).get("coordinates")
                if not coords:
                    continue
                props = feat.get("properties") or {}
                title = props.get("name", props.get("title", "Alert Event"))
                results.append({
                    "title": title[:200],
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "location": props.get("country", ""),
                    "alert_type": "rocket_alert",
                    "severity": "high",
                    "date": props.get("date", ""),
                    "url": props.get("url", ""),
                    "source": "GDELT",
                    "type": "rocket_alert",
                })
        except Exception as exc:
            logger.debug("GDELT rocket alerts: %s", exc)
        return results

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        results = await self._collect(
            client,
            self._from_tzevaadom,
            self._from_oref,
            self._from_gdelt_alerts,
        )
        logger.info("Rocket alerts: %d total from all sources", len(results))
        return results
