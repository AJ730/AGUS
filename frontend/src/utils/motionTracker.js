import * as Cesium from 'cesium'

const DEG_TO_RAD = Math.PI / 180
const EARTH_R = 6371000 // meters

/**
 * Extrapolates a new Cartesian3 position from current lat/lon + heading + speed
 * using great-circle dead reckoning.
 */
function extrapolate(lon, lat, headingDeg, speedKnots, elapsedMs, altM) {
  if (!speedKnots || speedKnots < 0.5) return null // stationary

  const speedMps = speedKnots * 0.514444
  const distM = speedMps * (elapsedMs / 1000)

  // Cap extrapolation at 60s to prevent wild drift between stale refreshes
  if (elapsedMs > 60000) return null

  const headingRad = headingDeg * DEG_TO_RAD
  const latRad = lat * DEG_TO_RAD
  const lonRad = lon * DEG_TO_RAD
  const angDist = distM / EARTH_R

  const sinLat = Math.sin(latRad)
  const cosLat = Math.cos(latRad)
  const sinAng = Math.sin(angDist)
  const cosAng = Math.cos(angDist)

  const newLatRad = Math.asin(sinLat * cosAng + cosLat * sinAng * Math.cos(headingRad))
  const newLonRad = lonRad + Math.atan2(
    Math.sin(headingRad) * sinAng * cosLat,
    cosAng - sinLat * Math.sin(newLatRad)
  )

  return Cesium.Cartesian3.fromDegrees(
    newLonRad / DEG_TO_RAD,
    newLatRad / DEG_TO_RAD,
    altM || 0
  )
}

/**
 * Updates positions of all entities in a data source that have _motionData.
 * Each entity._motionData = { lon, lat, alt, heading, speed (knots), timestamp }
 * Returns count of entities that were moved.
 */
export function updateEntityMotion(ds) {
  if (!ds || !ds.show) return 0
  const now = Date.now()
  let moved = 0
  const entities = ds.entities.values

  for (let i = 0; i < entities.length; i++) {
    const entity = entities[i]
    const md = entity._motionData
    if (!md) continue

    const elapsed = now - md.timestamp
    if (elapsed < 50) continue // skip if too recent (just created)

    const newPos = extrapolate(md.lon, md.lat, md.heading, md.speed, elapsed, md.alt)
    if (newPos) {
      entity.position = newPos
      moved++
    }
  }
  return moved
}
