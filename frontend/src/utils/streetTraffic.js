import * as Cesium from 'cesium'

// Cache fetched road data by tile key to avoid re-fetching
const _roadCache = new Map()
const MAX_CACHE_TILES = 20

/**
 * Fetch OSM roads for a bounding box via Overpass API.
 * Returns array of road polylines, each being an array of [lon, lat] pairs.
 */
async function fetchRoads(south, west, north, east) {
  const key = `${south.toFixed(2)},${west.toFixed(2)},${north.toFixed(2)},${east.toFixed(2)}`
  if (_roadCache.has(key)) return _roadCache.get(key)

  const query = `[out:json][timeout:15];way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential)$"](${south},${west},${north},${east});out geom;`

  try {
    const resp = await fetch('https://overpass-api.de/api/interpreter', {
      method: 'POST',
      body: `data=${encodeURIComponent(query)}`,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    if (!resp.ok) return []
    const data = await resp.json()

    const roads = []
    for (const el of (data.elements || [])) {
      if (!el.geometry || el.geometry.length < 2) continue
      const coords = el.geometry.map(g => [g.lon, g.lat])
      // Road type determines how many vehicles to place
      const highway = el.tags?.highway || 'residential'
      const density = highway === 'motorway' || highway === 'trunk' ? 3
        : highway === 'primary' ? 2 : 1
      roads.push({ coords, density, highway })
    }

    // Cache management
    if (_roadCache.size >= MAX_CACHE_TILES) {
      const firstKey = _roadCache.keys().next().value
      _roadCache.delete(firstKey)
    }
    _roadCache.set(key, roads)
    return roads
  } catch {
    return []
  }
}

/**
 * Generate vehicle positions along a road polyline.
 * Each vehicle has: position, direction, speed, progress along segment.
 */
function generateVehicles(road) {
  const vehicles = []
  const { coords, density } = road

  // Calculate total road length in degrees (approximate)
  let totalLen = 0
  const segLens = []
  for (let i = 0; i < coords.length - 1; i++) {
    const dx = coords[i + 1][0] - coords[i][0]
    const dy = coords[i + 1][1] - coords[i][1]
    const len = Math.sqrt(dx * dx + dy * dy)
    segLens.push(len)
    totalLen += len
  }

  if (totalLen < 0.0001) return vehicles // too short

  // Place vehicles at intervals
  const spacing = 0.002 // ~200m in degrees at mid-latitudes
  const numVehicles = Math.min(Math.floor(totalLen / spacing) * density, 15)

  for (let v = 0; v < numVehicles; v++) {
    // Random position along the road
    const progress = Math.random()
    // Random speed variation (0.00001 to 0.00004 degrees/frame ~ 30-80 km/h)
    const speed = 0.000015 + Math.random() * 0.000025
    // Direction: 0 = forward along coords, 1 = reverse (opposite lane)
    const direction = v % 2 === 0 ? 1 : -1

    vehicles.push({ progress, speed, direction, road })
  }

  return vehicles
}

/**
 * Interpolate position along road at given progress (0-1).
 * Returns [lon, lat] or null.
 */
function interpolateRoad(coords, progress) {
  if (coords.length < 2) return null

  // Calculate total length
  let totalLen = 0
  const cumLen = [0]
  for (let i = 0; i < coords.length - 1; i++) {
    const dx = coords[i + 1][0] - coords[i][0]
    const dy = coords[i + 1][1] - coords[i][1]
    totalLen += Math.sqrt(dx * dx + dy * dy)
    cumLen.push(totalLen)
  }

  const targetLen = progress * totalLen

  // Find segment
  for (let i = 0; i < cumLen.length - 1; i++) {
    if (targetLen >= cumLen[i] && targetLen <= cumLen[i + 1]) {
      const segLen = cumLen[i + 1] - cumLen[i]
      if (segLen < 1e-10) continue
      const t = (targetLen - cumLen[i]) / segLen
      const lon = coords[i][0] + t * (coords[i + 1][0] - coords[i][0])
      const lat = coords[i][1] + t * (coords[i + 1][1] - coords[i][1])
      return [lon, lat]
    }
  }
  return coords[coords.length - 1]
}

// ---- Main controller class ----

export class StreetTrafficController {
  constructor(viewer) {
    this._viewer = viewer
    this._active = false
    this._vehicles = []    // array of vehicle state objects
    this._points = null    // Cesium.PointPrimitiveCollection
    this._lastFetchLat = null
    this._lastFetchLon = null
    this._animFrameId = null
    this._fetching = false
  }

  /**
   * Called on each postRender — checks altitude and manages lifecycle.
   * @param {number} altKm - camera altitude in km
   * @param {number} lat - camera latitude in degrees
   * @param {number} lon - camera longitude in degrees
   */
  update(altKm, lat, lon) {
    if (altKm < 5) {
      if (!this._active) {
        this._activate()
      }
      // Re-fetch roads if camera moved significantly (>0.01 deg ~ 1km)
      if (!this._fetching && (
        this._lastFetchLat === null ||
        Math.abs(lat - this._lastFetchLat) > 0.01 ||
        Math.abs(lon - this._lastFetchLon) > 0.01
      )) {
        this._fetchAndPopulate(lat, lon, altKm)
      }
      this._animate()
    } else if (this._active) {
      this._deactivate()
    }
  }

  _activate() {
    this._active = true
    this._points = this._viewer.scene.primitives.add(
      new Cesium.PointPrimitiveCollection()
    )
  }

  _deactivate() {
    this._active = false
    this._vehicles = []
    if (this._points) {
      this._viewer.scene.primitives.remove(this._points)
      this._points = null
    }
  }

  async _fetchAndPopulate(lat, lon, altKm) {
    this._fetching = true
    this._lastFetchLat = lat
    this._lastFetchLon = lon

    // Viewport bounding box based on altitude
    const span = Math.min(altKm * 0.015, 0.05) // smaller area when closer
    const south = lat - span
    const north = lat + span
    const west = lon - span
    const east = lon + span

    const roads = await fetchRoads(south, west, north, east)

    // Clear old vehicles
    this._vehicles = []
    if (this._points) {
      this._points.removeAll()
    }

    // Generate vehicles for each road
    for (const road of roads) {
      const vehs = generateVehicles(road)
      for (const v of vehs) {
        const pos = interpolateRoad(v.road.coords, v.progress)
        if (!pos) continue

        // Add point primitive
        if (this._points) {
          const point = this._points.add({
            position: Cesium.Cartesian3.fromDegrees(pos[0], pos[1], 1),
            pixelSize: v.direction > 0 ? 4 : 3,
            color: v.direction > 0
              ? Cesium.Color.fromCssColorString('#fbbf24') // yellow headlight
              : Cesium.Color.fromCssColorString('#ef4444'), // red taillight
            scaleByDistance: new Cesium.NearFarScalar(100, 1.5, 5000, 0.3),
          })
          v._point = point
        }

        this._vehicles.push(v)
      }
    }

    this._fetching = false
    this._viewer.scene.requestRender()
  }

  _animate() {
    for (const v of this._vehicles) {
      // Move vehicle along road
      v.progress += v.speed * v.direction * 0.016 // ~60fps frame time

      // Wrap around
      if (v.progress > 1) v.progress -= 1
      if (v.progress < 0) v.progress += 1

      const pos = interpolateRoad(v.road.coords, v.progress)
      if (pos && v._point) {
        v._point.position = Cesium.Cartesian3.fromDegrees(pos[0], pos[1], 1)
      }
    }

    if (this._vehicles.length > 0) {
      this._viewer.scene.requestRender()
    }
  }

  destroy() {
    this._deactivate()
  }
}
