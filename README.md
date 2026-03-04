# AGUS - OSINT Intelligence Globe

Real-time global intelligence platform aggregating 35 free OSINT data sources onto an interactive 3D CesiumJS globe. Features GPU visual filters (CRT/NVG/FLIR/Anime/Targeting), Google Photorealistic 3D Tiles, real-time entity motion tracking, NASA satellite overlays, military aircraft detection (ADS-B dbFlags), naval vessel classification (5-layer AIS pipeline), threat intelligence, worldwide SDR receivers, and emergency squawk alerts.

## Demo

![Demo](demo.gif)

## Architecture

```
frontend/  React + CesiumJS (Vite build, nginx)    :3000 -> :80
backend/   FastAPI + httpx (Python 3.11, uvicorn)   :8000
```

### Data Sources (35 layers, 34,000+ records)

| Layer | Source | Records | Auth |
|---|---|---|---|
| Flights | airplanes.live + adsb.one + adsb.fi + adsb.lol + OpenSky (4-source batching) | ~8000+ | None |
| Conflicts | ACLED + Wikidata SPARQL + GDELT combined | ~200 | ACLED (optional) |
| Missile Tests | ACLED + GDELT + Wikidata + Reddit/Telegram cross-reference | ~522 | ACLED (optional) |
| News Events | GDELT GEO API | ~50 | None |
| Live News | GDELT GEO + BBC/Al Jazeera RSS | ~50 | None |
| CCTV Cameras | Windy API + Overpass OSM | ~600 | WINDY_API_KEY (optional) |
| Fire Hotspots | NASA FIRMS MODIS | ~8000 | None |
| Earthquakes | USGS GeoJSON | ~36 | None |
| Weather Alerts | GDACS RSS | ~187 | None |
| Nuclear/Radiation | Wikidata SPARQL + RadMon | ~426 | None |
| Vessels (AIS) | Digitraffic Finland (5-layer naval classification) | 3000 | None |
| Submarines | Wikidata SPARQL + Overpass | ~311 | None |
| Carriers | Google News + USNI + Naval News + GDELT + ADS-B | ~10 | None |
| Piracy | GDELT GEO API | ~8 | None |
| Security Events | ACLED + GDELT violence filter | ~200 | ACLED (optional) |
| Cyber Threats | AbuseIPDB + Tor Project | ~30 | ABUSEIPDB_API_KEY (optional) |
| Threat Intel | AlienVault OTX + URLhaus + DShield + Feodo Tracker + CISA KEV | ~87 | OTX_API_KEY (optional) |
| Military Bases | Overpass (node+way+relation) + Wikidata (5 types) + 35 strategic | ~1900 | None |
| Airspace | OpenAIP + GDELT fallback | ~500 | OPENAIP_API_KEY (optional) |
| Displacement | UNHCR API + GDELT | ~127 | None |
| Sanctions | OpenSanctions CSV | ~150 | None |
| Satellites | SatNOGS DB | ~201 | None |
| Airports | OurAirports CSV (with LiveATC links) | ~5257 | None |
| NOTAMs | GDELT GEO API | ~200 | None |
| Radio/SDR | KiwiSDR public directory | ~916 | None |
| Telegram OSINT | 48 RSS feeds (BBC, Al Jazeera, Bellingcat, etc.) | ~421 | None |
| Reddit OSINT | 18 subreddits (worldnews, CombatFootage, etc.) | ~400 | None |
| Rocket Alerts | OREF + Tzeva Adom + GDELT | ~50 | None |
| GeoConfirmed | osint-geo-extractor (GeoConfirmed + Bellingcat) | ~200 | None |
| Undersea Cables | TeleGeography GitHub | ~1914 | None |
| Live Streams | iptv-org community | ~168 | None |
| Equipment Losses | WarSpotting + GDELT | varies | None |
| Internet Outages | IODA + GDELT | varies | None |
| GPS Jamming | GPSJam + GDELT | ~14 | None |
| Natural Events | NASA EONET | ~200 | None |

## Quick Start

### Prerequisites
- Docker and Docker Compose
- (Optional) Google Maps API key for 3D Tiles and live traffic
- (Optional) Cesium Ion token for 3D Tiles fallback

### Setup

1. Create `.env` in the project root with optional API keys:
   ```bash
   # 3D Tiles & Live Traffic (optional but recommended)
   VITE_GOOGLE_MAPS_API_KEY=your_google_maps_key
   VITE_CESIUM_ION_TOKEN=your_cesium_ion_token

   # Backend API keys (all optional)
   ACLED_EMAIL=your_email@example.com
   ACLED_PASSWORD=your_acled_password
   WINDY_API_KEY=your_windy_key
   ABUSEIPDB_API_KEY=your_abuseipdb_key
   OPENAIP_API_KEY=your_openaip_key
   OTX_API_KEY=your_otx_key
   ```

2. Build and run:
   ```bash
   docker compose up --build
   ```

3. Open http://localhost:3000

## Features

### Visual Filters (GPU Post-Processing)
- **CRT** - Cathode-ray tube with scanlines, barrel distortion, chromatic aberration, green phosphor tint
- **NVG** - Night vision goggles with green monochrome, film grain, bloom glow
- **FLIR** - Thermal/infrared with Iron Bow color palette and Gaussian blur
- **Anime** - Studio Ghibli cel-shading with Sobel edge detection and color quantization
- **Targeting** - Military HUD reticle with crosshairs, range rings, corner brackets

### Map Modes
- **SAT** - High-res ESRI satellite imagery
- **HYB** - Satellite + CartoDB dark streets crossfade (altitude-adaptive)
- **DARK** - CartoDB Dark Matter basemap
- **NITE** - Dark basemap + NASA VIIRS nightlights overlay
- **3D** - Google Photorealistic 3D Tiles (requires API key) or Cesium Ion fallback

### Satellite Overlays (NASA GIBS)
- **THM** - VIIRS thermal hotspots
- **NLT** - Earth at Night (nightlights)
- **AER** - Aerosol optical depth
- **TRF** - Google Live Traffic tiles

### Real-Time Entity Motion
- Dead-reckoning position extrapolation for flights, vessels, and carriers
- Great-circle navigation formula updates positions every 200ms between API refreshes
- Vessels visibly glide across ocean at their real AIS speed + heading
- Aircraft smoothly fly along trajectory at reported speed

### Military Intelligence
- **Aircraft**: 4-source ADS-B batching + `dbFlags` military detection + ICAO24 hex ranges + callsign heuristics
- **Naval Vessels**: 5-layer AIS classification (MMSI ranges, name prefixes, ship types, callsigns, flag states) — 45+ live naval vessels
- **Bases**: 1900+ military installations from Overpass + Wikidata
- **Carriers**: Live news correlation from Google News + USNI + Naval News + GDELT + ADS-B

### Threat Intelligence
- **AlienVault OTX**: Pulse indicators with severity classification
- **URLhaus**: Active malware distribution URLs
- **DShield**: Top attacking IPs
- **Feodo Tracker**: Botnet C2 servers
- **CISA KEV**: Known exploited vulnerabilities

### Radio & Signals Intelligence
- **KiwiSDR**: 900+ worldwide SDR receivers — click to open web tuner
- **LiveATC**: Click any airport to open ATC radio feed

### OSINT Feeds
- **Telegram**: 48 curated RSS feeds from international news agencies and OSINT sources
- **Reddit**: 18 conflict/geopolitics subreddits with automatic geocoding
- **GeoConfirmed**: Verified geolocated conflict events from GeoConfirmed + Bellingcat
- **Rocket Alerts**: Israel rocket alert system (OREF + Tzeva Adom)

### Emergency Alerts
- **Squawk detection**: Automatic 7500 (hijack), 7600 (radio failure), 7700 (emergency) detection
- **Flashing red banner** at top of screen when emergency squawk codes are active

### Analytics
- Real-time entity counts for 12 tracked layers
- News ticker with live headlines from GDELT, Telegram, and Reddit feeds

### Camera Presets
- 15 cinematic presets with heading/pitch: Ukraine, Gaza, Taiwan Strait, Persian Gulf, Syria, Korean DMZ, and more

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Service health with per-source status |
| `GET /api/sources` | Detailed source info (TTL, freshness, errors) |
| `GET /api/flights` | Live aircraft positions (with military flags) |
| `GET /api/flights_viewport?lat=X&lon=Y&dist=Z` | On-demand viewport flight fetch |
| `GET /api/conflicts` | Conflict events (ACLED + GDELT + Wikidata) |
| `GET /api/missile_tests` | Missile/strike events with Reddit/Telegram cross-reference |
| `GET /api/fires` | Active fire hotspots (NASA FIRMS) |
| `GET /api/earthquakes` | Recent M2.5+ earthquakes (USGS) |
| `GET /api/vessels` | AIS vessel positions (with naval classification) |
| `GET /api/threat_intel` | Geo-located threat indicators |
| `GET /api/signals` | KiwiSDR receiver locations |
| `GET /api/airports` | Airports with LiveATC links |
| `GET /api/natural_events` | NASA EONET natural events |
| `GET /api/{layer}` | Any of the 35 layer endpoints |
| `GET /api/flight_detail/{icao24}` | Detailed aircraft info + track |
| `POST /api/analyze` | AI-powered region analysis (requires LLM backend) |
| `POST /api/correlate` | Cross-layer event correlation |

## Tech Stack

- **Backend**: FastAPI, httpx (async HTTP), APScheduler, GZip middleware
- **Frontend**: React 18, CesiumJS, Vite, GLSL shaders
- **Rendering**: GPU post-process filters, Google 3D Tiles, NASA GIBS WMTS, animated arcs
- **Deployment**: Docker Compose, nginx reverse proxy
- **Intelligence**: 35 OSINT sources, military detection heuristics, threat correlation, dead-reckoning motion
