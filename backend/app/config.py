"""
Agus OSINT Backend -- Configuration
=======================================
Centralised configuration for cache TTLs, HTTP client settings,
layer sources, and operational constants.
"""

from __future__ import annotations

import os

import httpx

# ---------------------------------------------------------------------------
# Operational constants
# ---------------------------------------------------------------------------
MAX_VESSELS: int = 3000
MAX_SATELLITES: int = 200
MAX_STARLINK: int = 30
MAX_FIRES: int = 5000
MAX_FLIGHTS: int = 5000
MAX_SANCTIONS: int = 200

# ---------------------------------------------------------------------------
# Optional API keys (loaded from environment)
# ---------------------------------------------------------------------------
ACLED_EMAIL: str = os.getenv("ACLED_EMAIL", "")
ACLED_PASSWORD: str = os.getenv("ACLED_PASSWORD", "")
ABUSEIPDB_API_KEY: str = os.getenv("ABUSEIPDB_API_KEY", "")
WINDY_API_KEY: str = os.getenv("WINDY_API_KEY", "")
OPENAIP_API_KEY: str = os.getenv("OPENAIP_API_KEY", "")
OTX_API_KEY: str = os.getenv("OTX_API_KEY", "")
UCDP_API_KEY: str = os.getenv("UCDP_API_KEY", "")

# Azure OpenAI (for LLM intelligence analysis)
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY: str = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

# ---------------------------------------------------------------------------
# HTTP client settings
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = httpx.Timeout(connect=15.0, read=45.0, write=10.0, pool=30.0)
CONNECTION_LIMITS = httpx.Limits(
    max_connections=200,
    max_keepalive_connections=50,
    keepalive_expiry=120,
)

# ---------------------------------------------------------------------------
# Layer configuration -- maps layer name to cache TTL and upstream URL
# ---------------------------------------------------------------------------
LAYER_CONFIG: dict[str, dict] = {
    "flights": {
        "ttl": 30,
        "source_url": "https://opensky-network.org/api/states/all (regional bbox)",
    },
    "conflicts": {
        "ttl": 3600,
        "source_url": "https://api.acleddata.com/acled/read",
    },
    "events": {
        "ttl": 900,
        "source_url": "https://api.gdeltproject.org/api/v2/geo/geo",
    },
    "fires": {
        "ttl": 1800,
        "source_url": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_24h.csv",
    },
    "vessels": {
        "ttl": 30,
        "source_url": "https://meri.digitraffic.fi/api/ais/v1/locations",
    },
    "cctv": {
        "ttl": 3600,
        "source_url": "https://api.windy.com/webcams/api/v3/webcams",
    },
    "satellites": {
        "ttl": 30,
        "source_url": "https://celestrak.org/NORAD/elements/gp.php (TLE groups)",
    },
    "earthquakes": {
        "ttl": 300,
        "source_url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson",
    },
    "nuclear": {
        "ttl": 86400,
        "source_url": "https://query.wikidata.org/sparql (nuclear plants)",
    },
    "weather_alerts": {
        "ttl": 900,
        "source_url": "https://www.gdacs.org/xml/rss.xml",
    },
    "terrorism": {
        "ttl": 3600,
        "source_url": "https://api.acleddata.com/acled/read (violence filter)",
    },
    "refugees": {
        "ttl": 21600,
        "source_url": "https://api.unhcr.org/population/v1/population/",
    },
    "piracy": {
        "ttl": 3600,
        "source_url": "https://api.gdeltproject.org/api/v2/geo/geo (maritime)",
    },
    "airspace": {
        "ttl": 86400,
        "source_url": "https://api.core.openaip.net/api/airspaces",
    },
    "sanctions": {
        "ttl": 86400,
        "source_url": "https://data.opensanctions.org/datasets/latest/default/targets.simple.csv",
    },
    "cyber": {
        "ttl": 3600,
        "source_url": "https://check.torproject.org/torbulkexitlist + AbuseIPDB",
    },
    "military_bases": {
        "ttl": 86400,
        "source_url": "https://overpass-api.de/api/interpreter (OSM military)",
    },
    "airports": {
        "ttl": 86400,
        "source_url": "https://davidmegginson.github.io/ourairports-data/airports.csv",
    },
    "notams": {
        "ttl": 21600,
        "source_url": "https://api.gdeltproject.org/api/v2/geo/geo (NOTAM/airspace)",
    },
    "submarines": {
        "ttl": 86400,
        "source_url": "https://query.wikidata.org/sparql (submarine bases)",
    },
    "carriers": {
        "ttl": 3600,
        "source_url": "Google News + USNI + Naval News + GDELT + ADS-B (live carrier positions)",
    },
    "news": {
        "ttl": 900,
        "source_url": "http://api.gdeltproject.org/api/v2/geo/geo (breaking news)",
    },
    "threat_intel": {
        "ttl": 1800,
        "source_url": "https://otx.alienvault.com/api/v1/pulses/activity + https://internetdb.shodan.io",
    },
    "signals": {
        "ttl": 86400,
        "source_url": "http://rx.linkfanel.net/kiwisdr_com.js (KiwiSDR directory)",
    },
    "missile_tests": {
        "ttl": 600,
        "source_url": "https://acleddata.com/api/acled/read (live strikes/bombings)",
    },
    "telegram_osint": {
        "ttl": 300,
        "source_url": "Telegram OSINT channels via RSS bridges (Aurora Intel, BNO, etc.)",
    },
    "rocket_alerts": {
        "ttl": 300,
        "source_url": "https://www.oref.org.il/WarningMessages/alert/alerts.json (OREF) + GDELT",
    },
    "geo_confirmed": {
        "ttl": 3600,
        "source_url": "GeoConfirmed + Bellingcat (osint-geo-extractor)",
    },
    "undersea_cables": {
        "ttl": 86400,
        "source_url": "https://www.submarinecablemap.com/api/v3/ (TeleGeography)",
    },
    "live_streams": {
        "ttl": 86400,
        "source_url": "Curated 24/7 live news broadcast streams (Al Jazeera, Sky, France24, etc.)",
    },
    "reddit_osint": {
        "ttl": 600,
        "source_url": "Reddit OSINT subreddits (worldnews, CombatFootage, geopolitics, CredibleDefense, etc.)",
    },
    "equipment_losses": {
        "ttl": 3600,
        "source_url": "https://ukr.warspotting.net/api/ (WarSpotting verified losses) + GDELT",
    },
    "internet_outages": {
        "ttl": 900,
        "source_url": "https://api.ioda.inetintel.cc.gatech.edu/v2/ (IODA) + GDELT",
    },
    "gps_jamming": {
        "ttl": 3600,
        "source_url": "Known EW zones (Eurocontrol/OPSGROUP) + GDELT GPS interference reports",
    },
    "natural_events": {
        "ttl": 1800,
        "source_url": "https://eonet.gsfc.nasa.gov/api/v3/events",
    },
}
