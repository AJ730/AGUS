# AGUS - OSINT Intelligence Globe

Real-time global intelligence platform aggregating 24 free OSINT data sources onto an interactive 3D CesiumJS globe. Features military aircraft detection (adsb.lol dbFlags), threat intelligence (Shodan InternetDB + AlienVault OTX), worldwide SDR receivers (KiwiSDR), naval military vessel classification, LiveATC airport radio, and emergency squawk alert banners.

## Architecture

```
frontend/  React + CesiumJS (Vite build, nginx)    :3000 -> :80
backend/   FastAPI + httpx (Python 3.11, uvicorn)   :8000
```

### Data Sources (24 layers)

| Layer | Source | Records | Auth |
|---|---|---|---|
| Flights | adsb.lol (dbFlags military detection) / OpenSky | ~8000+ | None |
| Conflicts | ACLED / Wikidata SPARQL / GDELT | ~200 | ACLED_EMAIL + ACLED_PASSWORD (optional) |
| News Events | GDELT GEO API | ~50 | None |
| Live News | GDELT GEO + BBC/Al Jazeera RSS | ~50 | None |
| CCTV Cameras | Windy API / GDELT fallback | varies | WINDY_API_KEY (optional) |
| Fire Hotspots | NASA FIRMS MODIS | ~15000 | None |
| Earthquakes | USGS GeoJSON | ~40 | None |
| Weather Alerts | GDACS RSS | ~160 | None |
| Radiation | Wikidata SPARQL + RadMon | ~425 | None |
| Vessels (AIS) | Digitraffic Finland (military classification) | 3000 | None |
| Submarines | Wikidata SPARQL + Overpass | ~300 | None |
| Carriers | Wikidata SPARQL | ~43 | None |
| Piracy | GDELT GEO API | varies | None |
| Security Events | ACLED / GDELT | varies | ACLED (optional) |
| Cyber Threats | AbuseIPDB + Tor Project | ~50 | ABUSEIPDB_API_KEY (optional) |
| **Threat Intel** | **Shodan InternetDB + AlienVault OTX** | **~20+** | **OTX_API_KEY (optional)** |
| Military Bases | Overpass / Wikidata | ~1900 | None |
| Airspace | OpenAIP / GDELT | varies | OPENAIP_API_KEY (optional) |
| Displacement | UNHCR API / GDELT | ~127 | None |
| Sanctions | OpenSanctions CSV | ~150 | None |
| Satellites | SatNOGS DB | ~200 | None |
| Airports | OurAirports CSV (with LiveATC links) | ~5200 | None |
| NOTAMs | GDELT GEO API | varies | None |
| **Radio/SDR** | **KiwiSDR public directory** | **~900+** | **None** |

## Quick Start

### Prerequisites
- Docker and Docker Compose

### Setup

1. Copy environment template and add API keys:
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your keys (all optional for basic functionality)
   ```

2. Build and run:
   ```bash
   docker compose up --build
   ```

3. Open http://localhost:3000

## API Keys & Signups

All 24 layers work without API keys using free/open data sources. Optional keys unlock premium data or higher rate limits.

### Free (no signup needed)

These sources require no registration and work out of the box:

| Source | Used By | Notes |
|---|---|---|
| [adsb.lol](https://api.adsb.lol/) | Flights | Free ADS-B aggregator, includes `dbFlags` for military detection |
| [OpenSky Network](https://opensky-network.org/) | Flights (fallback) | Aggressive rate limiting (1 req/10s anonymous) |
| [USGS Earthquake API](https://earthquake.usgs.gov/earthquakes/feed/) | Earthquakes | GeoJSON feed, M2.5+ events |
| [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | Fire Hotspots | MODIS active fire data, 24h window |
| [Digitraffic AIS](https://www.digitraffic.fi/en/marine-traffic/) | Vessels | Finnish Transport Agency, global AIS data |
| [GDELT Project](https://api.gdeltproject.org/) | News, Events, Piracy, NOTAMs, CCTV fallback | GEO API, **use HTTP not HTTPS in Docker** |
| [GDACS](https://www.gdacs.org/) | Weather Alerts | Global Disaster Alert RSS |
| [UNHCR API](https://api.unhcr.org/) | Displacement | Refugee/IDP population data |
| [Wikidata SPARQL](https://query.wikidata.org/) | Nuclear, Submarines, Carriers, Military Bases, Conflicts | Linked open data |
| [Overpass API](https://overpass-api.de/) | Military Bases, Submarines | OpenStreetMap query engine |
| [OpenSanctions](https://www.opensanctions.org/) | Sanctions | CSV dataset, auto-updated |
| [SatNOGS](https://db.satnogs.org/) | Satellites | TLE database for active satellites |
| [OurAirports](https://ourairports.com/) | Airports | CSV with ICAO/IATA codes |
| [Tor Project](https://check.torproject.org/) | Cyber Threats | Bulk exit node list |
| [Shodan InternetDB](https://internetdb.shodan.io/) | Threat Intel | Free, no key, open ports + CVEs per IP |
| [KiwiSDR Directory](http://rx.linkfanel.net/) | Radio/SDR | Community JS mirror of KiwiSDR.com |
| [LiveATC](https://www.liveatc.net/) | Airports (links) | ATC radio links (not embedded) |
| [RadMon](https://radmon.org/) | Radiation | Community radiation monitoring |
| [ip-api.com](http://ip-api.com/) | Threat Intel (geolocation) | Batch IP geolocation, 100 req/min |

### Optional Signups (enhanced data)

| Service | Env Variable | Free Tier | Signup URL |
|---|---|---|---|
| **ACLED** | `ACLED_EMAIL` + `ACLED_PASSWORD` | Free for researchers | [acleddata.com/register](https://acleddata.com/register/) |
| **Windy Webcams** | `WINDY_API_KEY` | 1000 req/day | [api.windy.com/keys](https://api.windy.com/keys) |
| **AbuseIPDB** | `ABUSEIPDB_API_KEY` | 1000 req/day | [abuseipdb.com/register](https://www.abuseipdb.com/register) |
| **OpenAIP** | `OPENAIP_API_KEY` | Free tier available | [openaip.net/users/sign_up](https://www.openaip.net/users/sign_up) |
| **AlienVault OTX** | `OTX_API_KEY` | Free, unlimited | [otx.alienvault.com/accounts/signup](https://otx.alienvault.com/accounts/signup/) |

### Environment Variables

Create `backend/.env` with any of these optional keys:

```bash
# Conflict data (ACLED)
ACLED_EMAIL=your_email@example.com
ACLED_PASSWORD=your_acled_password

# Live webcam feeds
WINDY_API_KEY=your_windy_key

# Enhanced cyber threat data
ABUSEIPDB_API_KEY=your_abuseipdb_key

# Airspace zone polygons
OPENAIP_API_KEY=your_openaip_key

# AlienVault OTX threat intelligence (more pulses with key)
OTX_API_KEY=your_otx_key
```

## Features

### Military Intelligence
- **Aircraft**: adsb.lol `dbFlags & 1` detection + callsign/ICAO24 prefix heuristics (70+ military prefixes)
- **Vessels**: AIS ship_type 35 (military) / 55 (law enforcement) classification with distinct warship icons
- **Bases**: 1900+ military installations from Overpass + Wikidata

### Threat Intelligence
- **Shodan InternetDB**: Geo-located exposed hosts with open ports + CVEs (no key needed)
- **AlienVault OTX**: Pulse indicators (IPv4, domains) with severity classification
- **Crosshair icons** color-coded by severity: critical (red), high (rose), medium (orange), low (yellow)

### Radio & Signals Intelligence
- **KiwiSDR**: 900+ worldwide SDR receivers — click to open web tuner
- **LiveATC**: Click any airport to open ATC radio feed

### Emergency Alerts
- **Squawk detection**: Automatic 7500 (hijack), 7600 (radio failure), 7700 (emergency) detection
- **Flashing red banner** at top of screen when emergency squawk codes are active

### Analytics
- Real-time entity counts for Flights, Conflicts, Earthquakes, Fires, News, Threats

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Service health with per-source status |
| `GET /api/sources` | Detailed source info (TTL, freshness, errors) |
| `GET /api/flights` | Live aircraft positions (with military flags) |
| `GET /api/conflicts` | Conflict events |
| `GET /api/fires` | Active fire hotspots |
| `GET /api/earthquakes` | Recent M2.5+ earthquakes |
| `GET /api/vessels` | AIS vessel positions (with military classification) |
| `GET /api/threat_intel` | Geo-located threat indicators (OTX + Shodan) |
| `GET /api/signals` | KiwiSDR receiver locations |
| `GET /api/airports` | Airports with LiveATC links |
| `GET /api/{layer}` | Any of the 24 layer endpoints |
| `GET /api/flight_detail/{icao24}` | Detailed aircraft info + track |

## Development

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Tech Stack

- **Backend**: FastAPI, httpx (async HTTP), APScheduler, GZip middleware
- **Frontend**: React 18, CesiumJS, Vite
- **Deployment**: Docker Compose, nginx reverse proxy
- **Intelligence**: 24 OSINT sources, military detection heuristics, threat correlation
