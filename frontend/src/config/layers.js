// Layer configuration - ALL 20 OSINT layers
export const LAYERS = {
  flights:        { label: 'Flights',         group: 'Intelligence',    color: '#fbbf24', refreshMs: 30000 },
  conflicts:      { label: 'Conflicts',       group: 'Intelligence',    color: '#ef4444', refreshMs: 300000 },
  events:         { label: 'News Events',     group: 'Intelligence',    color: '#f97316', refreshMs: 300000 },
  news:           { label: 'Live News',      group: 'Intelligence',    color: '#10b981', refreshMs: 300000 },
  cctv:           { label: 'CCTV Cameras',    group: 'Intelligence',    color: '#22c55e', refreshMs: 600000 },
  fires:          { label: 'Fire Hotspots',   group: 'Environmental',   color: '#f97316', refreshMs: 300000 },
  earthquakes:    { label: 'Earthquakes',     group: 'Environmental',   color: '#eab308', refreshMs: 300000 },
  weather_alerts: { label: 'Weather Alerts',  group: 'Environmental',   color: '#a855f7', refreshMs: 600000 },
  nuclear:        { label: 'Radiation',       group: 'Environmental',   color: '#84cc16', refreshMs: 600000 },
  vessels:        { label: 'Vessels (AIS)',    group: 'Maritime',        color: '#3b82f6', refreshMs: 30000 },
  submarines:     { label: 'Submarines',       group: 'Maritime',        color: '#0ea5e9', refreshMs: 3600000 },
  carriers:       { label: 'Carriers',        group: 'Maritime',        color: '#6366f1', refreshMs: 3600000 },
  piracy:         { label: 'Piracy Zones',    group: 'Maritime',        color: '#1e293b', refreshMs: 600000 },
  terrorism:      { label: 'Security Events', group: 'Security',        color: '#b91c1c', refreshMs: 600000 },
  cyber:          { label: 'Cyber Threats',   group: 'Security',        color: '#8b5cf6', refreshMs: 600000 },
  threat_intel:   { label: 'Threat Intel',    group: 'Security',        color: '#f43f5e', refreshMs: 600000 },
  military_bases: { label: 'Military Bases',  group: 'Security',        color: '#16a34a', refreshMs: 3600000 },
  airspace:       { label: 'Airspace',        group: 'Security',        color: '#dc2626', refreshMs: 3600000 },
  refugees:       { label: 'Displacement',    group: 'Humanitarian',    color: '#06b6d4', refreshMs: 3600000 },
  sanctions:      { label: 'Sanctions',       group: 'Humanitarian',    color: '#d97706', refreshMs: 3600000 },
  satellites:     { label: 'Satellites',       group: 'Space',           color: '#e2e8f0', refreshMs: 30000 },
  airports:       { label: 'Airports',        group: 'Infrastructure',  color: '#64748b', refreshMs: 86400000 },
  notams:         { label: 'NOTAMs',          group: 'Infrastructure',  color: '#f43f5e', refreshMs: 3600000 },
  signals:        { label: 'Radio/SDR',       group: 'Intelligence',    color: '#a78bfa', refreshMs: 86400000 },
}

export const PRESETS = [
  { name: 'Global',           lon: 20,     lat: 20,   alt: 20000000 },
  { name: 'Middle East',      lon: 44,     lat: 31,   alt: 3500000 },
  { name: 'Ukraine',          lon: 32,     lat: 49,   alt: 2500000 },
  { name: 'Africa Sahel',     lon: 2,      lat: 15,   alt: 4500000 },
  { name: 'South China Sea',  lon: 115,    lat: 12,   alt: 4000000 },
  { name: 'Horn of Africa',   lon: 48,     lat: 8,    alt: 3000000 },
  { name: 'Korea',            lon: 127,    lat: 37,   alt: 1500000 },
  { name: 'Taiwan Strait',    lon: 120,    lat: 24,   alt: 1500000 },
  { name: 'E Mediterranean',  lon: 34,     lat: 34,   alt: 2000000 },
  { name: 'Gaza',             lon: 34.47,  lat: 31.5, alt: 500000 },
]

// Default layers that are visible on initial load
export const DEFAULT_VISIBLE_LAYERS = ['flights', 'conflicts', 'fires', 'earthquakes', 'cctv', 'news']

// Group layers by their group property
export function groupLayers(layers) {
  const groups = {}
  for (const [key, cfg] of Object.entries(layers)) {
    if (!groups[cfg.group]) groups[cfg.group] = []
    groups[cfg.group].push({ key, ...cfg })
  }
  return groups
}
