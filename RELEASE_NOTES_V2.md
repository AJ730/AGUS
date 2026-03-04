# AGUS v2.0 — Release Notes

## Overview

AGUS v2.0 is a major upgrade from the initial release, expanding from 24 to **35 OSINT data sources** and adding **10,000+ lines** of new code across backend and frontend. This release introduces GPU visual filters, real-time entity motion, military intelligence classification, animated attack visualization, AI-powered analysis, and 15 new data layers.

---

## New Features

### GPU Post-Processing Visual Filters
Five shader-based visual filters that transform the globe into specialized intelligence visualization modes:
- **CRT** — Cathode-ray tube with scanlines, barrel distortion, chromatic aberration, and green phosphor tint
- **NVG** — Night vision goggles with green monochrome, film grain, and bloom glow
- **FLIR** — Thermal/infrared with Iron Bow color palette and Gaussian blur
- **Anime** — Studio Ghibli cel-shading with Sobel edge detection and color quantization
- **Targeting** — Military HUD reticle with crosshairs, range rings, and corner brackets

### Real-Time Entity Motion Tracking
- Dead-reckoning position extrapolation for flights, vessels, and carriers
- Great-circle navigation formula updates entity positions every 200ms between API refreshes
- Ships visibly glide across oceans at real AIS speed + heading
- Aircraft smoothly fly along trajectory at reported speed
- 60-second extrapolation cap prevents drift from stale data

### NASA GIBS Satellite Overlays
Four overlay layers from NASA Global Imagery Browse Services (no API key required):
- **THM** — VIIRS thermal hotspots
- **NLT** — Earth at Night (nightlights)
- **AER** — Aerosol optical depth (smoke/dust)
- **TRF** — Google Live Traffic tiles

### Google Photorealistic 3D Tiles
- Full 3D building and terrain rendering via Google Maps API
- Cesium Ion fallback when Google API key unavailable
- Entities properly anchored to ground in 3D mode

### Map Modes
Five basemap styles with altitude-adaptive rendering:
- **SAT** — High-res ESRI satellite imagery
- **HYB** — Satellite + CartoDB dark streets crossfade
- **DARK** — CartoDB Dark Matter basemap
- **NITE** — Dark basemap + NASA VIIRS nightlights overlay
- **3D** — Google Photorealistic 3D Tiles

### Animated Attack/Movement Arcs
- Great-circle trajectory arcs for missile strikes, airstrikes, and cyber attacks
- Staggered growth animations with glow effects and trail lines
- Expanding impact circles at target locations
- Origin-to-target visualization for geopolitical events

### Military Aircraft Detection
- 4-source ADS-B batching (airplanes.live, adsb.one, adsb.fi, adsb.lol) + OpenSky
- `dbFlags` bit 0 military detection from ADS-B APIs
- ICAO24 hex range database covering 28+ countries' military forces
- Civilian airline override prevents false positives
- hexdb.io API enrichment for aircraft registration and operator details
- Emergency squawk detection (7500 hijack, 7600 radio failure, 7700 emergency) with flashing banner

### Naval Vessel Classification (5-Layer Pipeline)
- MMSI range heuristics for military vessel identification
- Curated military MMSI database (US Navy carriers, NATO warships, etc.)
- AIS ship type code classification
- Vessel name pattern matching for warship identification
- Flag state + callsign analysis
- 45+ live naval vessels identified per refresh

### AI-Powered Region Analysis
- Azure OpenAI integration for structured intelligence briefings
- Threat level assessment (LOW/MEDIUM/HIGH/CRITICAL)
- Predictions with confidence levels
- Situation reports based on multi-layer OSINT data correlation

### Cinematic Camera Presets
15 presets with heading/pitch angles for dramatic viewing:
Ukraine, Gaza, Israel, Taiwan Strait, Persian Gulf, South China Sea, Korea, Iran, Red Sea, Myanmar, E Mediterranean, Horn of Africa, Africa Sahel, Middle East, Global

---

## New Data Layers (11 new sources)

| Layer | Source | Records | Description |
|---|---|---|---|
| Missile Tests/Strikes | ACLED + GDELT + Wikidata + Reddit/Telegram | ~522 | Cross-referenced missile and strike events |
| Telegram OSINT | 48 RSS feeds (BBC, Al Jazeera, Bellingcat, etc.) | ~441 | International news and OSINT intelligence feeds |
| Reddit OSINT | 18 subreddits (worldnews, CombatFootage, etc.) | ~399 | Conflict and geopolitics community intelligence |
| Rocket Alerts | OREF + Tzeva Adom + GDELT | ~50 | Israeli rocket alert system with geocoded locations |
| GeoConfirmed | osint-geo-extractor (GeoConfirmed + Bellingcat) | ~200 | Verified geolocated conflict events |
| Undersea Cables | TeleGeography GitHub | ~1,914 | Global submarine cable infrastructure |
| Live Streams | iptv-org community directory | ~168 | Worldwide live TV streams |
| Equipment Losses | WarSpotting + GDELT | varies | Tracked military equipment losses |
| Internet Outages | IODA + GDELT | varies | Global internet connectivity disruptions |
| GPS Jamming | GPSJam + GDELT | ~14 | GPS interference and jamming zones |
| Natural Events | NASA EONET | ~200 | Wildfires, volcanic eruptions, severe storms, icebergs |

---

## Enhanced Existing Layers

- **Flights**: 4-source concurrent batching across 57 global regions (~8,000+ aircraft). On-demand viewport fetch when user zooms below 500km altitude
- **Vessels**: 5-layer military naval classification pipeline. Dead-reckoning motion tracking
- **Carriers**: Live news correlation from Google News + USNI + Naval News + GDELT + ADS-B (removed inaccurate Wikidata home port data)
- **Conflicts**: Combined ACLED + Wikidata SPARQL + GDELT for broader coverage
- **Piracy**: Enhanced with Houthi/Red Sea attack tracking, GDELT TV mentions, maritime security news
- **Cyber Threats**: Added Shodan InternetDB enrichment, Tor exit node geolocation
- **Threat Intel**: Added Feodo Tracker botnet C2s, CISA KEV exploited vulnerabilities, DShield top attackers
- **Military Bases**: Overpass (node+way+relation) + Wikidata (5 types) + 35 hardcoded strategic bases (~2,000 total)
- **CCTV**: Added Windy API integration alongside Overpass OSM

---

## Frontend Improvements

- **React.memo** on all components for render optimization
- **requestRenderMode** with explicit `scene.requestRender()` — no unnecessary GPU frames
- **Inline styles extracted to CSS classes** across AnalysisPanel, VideoPanel, RadioPanel
- **Billboard depth testing** — entities visible when zoomed in, properly hidden behind earth at globe scale
- **FXAA + devicePixelRatio** for crisp GPU rendering
- **News ticker** with live headlines from GDELT, Telegram, and Reddit feeds
- **Analytics cards** — real-time entity counts for 12 tracked layers
- **Video panel** — embedded live stream player
- **Radio panel** — KiwiSDR and LiveATC integration
- **Analysis panel** — AI-powered intelligence briefing display

---

## Backend Improvements

- **BaseFetcher ABC pattern** — all 35 fetchers inherit from a common base class
- **Wave-based prefetching** — 4-wave startup (quick → medium → heavy → GDELT) with rate limit protection
- **CacheManager** — per-slot TTL with 30s retry for empty results
- **GZip middleware** on all responses (minimum_size=500)
- **Specific exception handling** — replaced bare `except Exception:` with typed catches across all routes
- **Type hints** added to all helper functions
- **Flight batching** — 4 concurrent ADS-B sources per 1.1s cycle (~16s for 57 regions)
- **GDELT rate limiting** — 2s sequential delays to avoid 429s from Docker
- **Cross-layer correlation** — `/api/correlate` endpoint for multi-source event matching
- **Military hex database** — `mil_hex_db.py` with ICAO24 ranges for 28+ countries

---

## API Endpoints (New)

| Endpoint | Description |
|---|---|
| `GET /api/missile_tests` | Missile/strike events with OSINT cross-reference |
| `GET /api/telegram_osint` | Telegram OSINT feed aggregation |
| `GET /api/reddit_osint` | Reddit OSINT feed aggregation |
| `GET /api/rocket_alerts` | Israeli rocket alert system |
| `GET /api/geo_confirmed` | GeoConfirmed verified events |
| `GET /api/undersea_cables` | Submarine cable infrastructure |
| `GET /api/live_streams` | Live TV stream directory |
| `GET /api/equipment_losses` | Military equipment loss tracking |
| `GET /api/internet_outages` | Internet connectivity disruptions |
| `GET /api/gps_jamming` | GPS jamming zones |
| `GET /api/natural_events` | NASA EONET natural events |
| `GET /api/flights_viewport` | On-demand viewport flight fetch |
| `POST /api/analyze` | AI-powered region analysis |
| `POST /api/correlate` | Cross-layer event correlation |

---

## Performance

- **34,000+ records** across 35 data sources
- **8,600+ aircraft** tracked simultaneously via 4-source batching
- **3,000 AIS vessels** with military classification
- **200ms motion refresh** for smooth entity movement
- **5fps dead-reckoning** updates between API refreshes
- **Wave-based startup** loads all sources in ~5 minutes

---

## Stats

- **10,490 lines added**, 799 removed across 64 files
- **11 new data fetchers**, 7 enhanced existing fetchers
- **5 new frontend utilities** (visual filters, GIBS, traffic, arcs, motion tracker)
- **4 new UI components** (AnalysisPanel, VideoPanel, RadioPanel, AnalyticsCards)
- **15 camera presets** with cinematic heading/pitch angles
