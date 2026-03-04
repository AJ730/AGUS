// Layer configuration - ALL OSINT layers
export const LAYERS = {
  flights:         { label: 'Flights',          group: 'Intelligence',    color: '#fbbf24', refreshMs: 30000 },
  conflicts:       { label: 'Conflicts',        group: 'Intelligence',    color: '#ef4444', refreshMs: 300000 },
  events:          { label: 'News Events',      group: 'Intelligence',    color: '#f97316', refreshMs: 300000 },
  news:            { label: 'Live News',        group: 'Intelligence',    color: '#10b981', refreshMs: 300000 },
  telegram_osint:  { label: 'Telegram OSINT',   group: 'Intelligence',    color: '#0088cc', refreshMs: 300000 },
  cctv:            { label: 'CCTV Cameras',     group: 'Intelligence',    color: '#22c55e', refreshMs: 600000 },
  fires:           { label: 'Fire Hotspots',    group: 'Environmental',   color: '#f97316', refreshMs: 300000 },
  earthquakes:     { label: 'Earthquakes',      group: 'Environmental',   color: '#eab308', refreshMs: 300000 },
  weather_alerts:  { label: 'Weather Alerts',   group: 'Environmental',   color: '#a855f7', refreshMs: 600000 },
  nuclear:         { label: 'Radiation',        group: 'Environmental',   color: '#84cc16', refreshMs: 600000 },
  vessels:         { label: 'Vessels (AIS)',     group: 'Maritime',        color: '#3b82f6', refreshMs: 30000 },
  submarines:      { label: 'Submarines',        group: 'Maritime',        color: '#0ea5e9', refreshMs: 3600000 },
  carriers:        { label: 'Carriers',         group: 'Maritime',        color: '#6366f1', refreshMs: 3600000 },
  piracy:          { label: 'Piracy Zones',     group: 'Maritime',        color: '#1e293b', refreshMs: 600000 },
  undersea_cables: { label: 'Undersea Cables',  group: 'Infrastructure',  color: '#06b6d4', refreshMs: 86400000 },
  terrorism:       { label: 'Security Events',  group: 'Security',        color: '#b91c1c', refreshMs: 600000 },
  cyber:           { label: 'Cyber Threats',    group: 'Security',        color: '#8b5cf6', refreshMs: 600000 },
  threat_intel:    { label: 'Threat Intel',     group: 'Security',        color: '#f43f5e', refreshMs: 600000 },
  rocket_alerts:   { label: 'Rocket Alerts',    group: 'Security',        color: '#ff0000', refreshMs: 60000 },
  military_bases:  { label: 'Military Bases',   group: 'Security',        color: '#16a34a', refreshMs: 3600000 },
  airspace:        { label: 'Airspace',         group: 'Security',        color: '#dc2626', refreshMs: 3600000 },
  missile_tests:   { label: 'Strikes/Bombs',   group: 'Security',        color: '#dc2626', refreshMs: 600000 },
  geo_confirmed:   { label: 'GeoConfirmed',    group: 'Intelligence',    color: '#14b8a6', refreshMs: 3600000 },
  refugees:        { label: 'Displacement',     group: 'Humanitarian',    color: '#06b6d4', refreshMs: 3600000 },
  sanctions:       { label: 'Sanctions',        group: 'Humanitarian',    color: '#d97706', refreshMs: 3600000 },
  satellites:      { label: 'Satellites',        group: 'Space',           color: '#e2e8f0', refreshMs: 30000 },
  airports:        { label: 'Airports',         group: 'Infrastructure',  color: '#64748b', refreshMs: 86400000 },
  notams:          { label: 'NOTAMs',           group: 'Infrastructure',  color: '#f43f5e', refreshMs: 3600000 },
  signals:         { label: 'Radio/SDR',        group: 'Intelligence',    color: '#a78bfa', refreshMs: 86400000 },
  live_streams:    { label: 'Live TV',          group: 'Intelligence',    color: '#ec4899', refreshMs: 86400000 },
  reddit_osint:    { label: 'Reddit OSINT',     group: 'Intelligence',    color: '#ff4500', refreshMs: 600000 },
  equipment_losses:{ label: 'Equipment Losses', group: 'Security',        color: '#92400e', refreshMs: 3600000 },
  internet_outages:{ label: 'Net Outages',      group: 'Infrastructure',  color: '#7c3aed', refreshMs: 900000 },
  gps_jamming:     { label: 'GPS Jamming',      group: 'Security',        color: '#e11d48', refreshMs: 3600000 },
  natural_events:  { label: 'Natural Events',   group: 'Environmental',   color: '#ff6b35', refreshMs: 1800000 },
  space_weather:   { label: 'Space Weather',   group: 'Space',           color: '#c084fc', refreshMs: 300000 },
  air_quality:     { label: 'Air Quality',     group: 'Environmental',   color: '#4ade80', refreshMs: 1800000 },
  cyclones:        { label: 'Cyclones',        group: 'Environmental',   color: '#38bdf8', refreshMs: 600000 },
  volcanoes:       { label: 'Volcanoes',       group: 'Environmental',   color: '#ef4444', refreshMs: 1800000 },
  asteroids:       { label: 'Asteroids/NEOs',  group: 'Space',           color: '#fbbf24', refreshMs: 86400000 },
  radiosondes:     { label: 'Radiosondes',     group: 'Space',           color: '#67e8f9', refreshMs: 120000 },
  disease_outbreaks:{ label: 'Disease Outbreaks', group: 'Humanitarian', color: '#f472b6', refreshMs: 3600000 },
  border_crossings:{ label: 'Border Waits',    group: 'Infrastructure',  color: '#a3e635', refreshMs: 600000 },
  mastodon_osint:  { label: 'Mastodon OSINT',  group: 'Intelligence',    color: '#6366f1', refreshMs: 600000 },
  space_launches:  { label: 'Space Launches', group: 'Space',           color: '#f59e0b', refreshMs: 300000 },
  protests:        { label: 'Protests',       group: 'Security',        color: '#f97316', refreshMs: 600000 },
  critical_infrastructure: { label: 'Infrastructure', group: 'Infrastructure', color: '#94a3b8', refreshMs: 3600000 },
  deforestation:   { label: 'Deforestation',  group: 'Environmental',   color: '#22c55e', refreshMs: 1800000 },
  n2yo_satellites: { label: 'N2YO Satellites', group: 'Space',          color: '#60a5fa', refreshMs: 60000 },
}

export const PRESETS = [
  { name: 'Global',           lon: 20,     lat: 20,   alt: 20000000, heading: 0,   pitch: -90 },
  { name: 'Middle East',      lon: 44,     lat: 31,   alt: 3500000,  heading: 0,   pitch: -70 },
  { name: 'Ukraine',          lon: 37,     lat: 48,   alt: 2000000,  heading: 45,  pitch: -25 },
  { name: 'Africa Sahel',     lon: 2,      lat: 15,   alt: 4500000,  heading: 0,   pitch: -75 },
  { name: 'South China Sea',  lon: 115,    lat: 12,   alt: 4000000,  heading: -20, pitch: -60 },
  { name: 'Horn of Africa',   lon: 48,     lat: 8,    alt: 3000000,  heading: 10,  pitch: -55 },
  { name: 'Korea',            lon: 127,    lat: 37,   alt: 1500000,  heading: 0,   pitch: -35 },
  { name: 'Taiwan Strait',    lon: 120,    lat: 24,   alt: 1500000,  heading: 90,  pitch: -20 },
  { name: 'E Mediterranean',  lon: 34,     lat: 34,   alt: 2000000,  heading: 15,  pitch: -45 },
  { name: 'Gaza',             lon: 34.47,  lat: 31.42,alt: 50000,    heading: -30, pitch: -30 },
  { name: 'Israel',           lon: 34.8,   lat: 31.5, alt: 800000,   heading: 0,   pitch: -50 },
  { name: 'Red Sea',          lon: 39,     lat: 18,   alt: 3000000,  heading: 0,   pitch: -60 },
  { name: 'Persian Gulf',     lon: 56.3,   lat: 26.6, alt: 500000,   heading: 90,  pitch: -20 },
  { name: 'Myanmar',          lon: 96,     lat: 19,   alt: 2500000,  heading: 0,   pitch: -55 },
  { name: 'Iran',             lon: 53,     lat: 32,   alt: 2000000,  heading: -15, pitch: -40 },
]

// Default layers that are visible on initial load
export const DEFAULT_VISIBLE_LAYERS = ['flights', 'conflicts', 'fires', 'earthquakes', 'cctv', 'news', 'missile_tests', 'telegram_osint', 'rocket_alerts']

// Group layers by their group property
export function groupLayers(layers) {
  const groups = {}
  for (const [key, cfg] of Object.entries(layers)) {
    if (!groups[cfg.group]) groups[cfg.group] = []
    groups[cfg.group].push({ key, ...cfg })
  }
  return groups
}
