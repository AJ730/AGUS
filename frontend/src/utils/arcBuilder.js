import * as Cesium from 'cesium'

/**
 * Build animated arcs (great-circle polylines) for attack/movement events.
 * Enhanced with animated growth, trail effects, and impact flash.
 *
 * Usage: call buildArcs(ds, arcData) where arcData is an array of:
 *   { fromLon, fromLat, toLon, toLat, color, label, width, type }
 */

// Generate intermediate points along a great circle arc
function greatCirclePoints(fromLon, fromLat, toLon, toLat, numPoints = 40, maxAlt = 200000) {
  const positions = []
  const from = Cesium.Cartographic.fromDegrees(fromLon, fromLat)
  const to = Cesium.Cartographic.fromDegrees(toLon, toLat)

  for (let i = 0; i <= numPoints; i++) {
    const t = i / numPoints
    const lat = from.latitude + (to.latitude - from.latitude) * t
    const lon = from.longitude + (to.longitude - from.longitude) * t
    // Parabolic altitude curve (peaks in middle)
    const altFactor = 4 * t * (1 - t)
    const alt = altFactor * maxAlt

    positions.push(Cesium.Cartesian3.fromRadians(lon, lat, alt))
  }
  return positions
}

// Calculate distance between two lon/lat points in km
function distanceKm(lon1, lat1, lon2, lat2) {
  const R = 6371
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLon = (lon2 - lon1) * Math.PI / 180
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

// Color lookup by event type
const ARC_COLORS = {
  missile_strike: '#ff0000',
  missile_test: '#ff0000',
  airstrike: '#ef4444',
  drone_strike: '#a855f7',
  shelling: '#f97316',
  bombing: '#dc2626',
  suicide_bombing: '#b91c1c',
  explosion: '#f97316',
  strike_report: '#ef4444',
  nuclear_test: '#f59e0b',
  cyber: '#8b5cf6',
  default: '#ef4444',
}

/**
 * Build animated arcs on the globe with growth animation and impact effects.
 * @param {Cesium.CustomDataSource} ds - DataSource to add arcs to
 * @param {Array} arcData - Array of arc descriptors
 */
export function buildArcs(ds, arcData) {
  const startTime = Date.now()

  for (let i = 0; i < arcData.length; i++) {
    const arc = arcData[i]
    const { fromLon, fromLat, toLon, toLat, label = '', width = 3, type = 'default' } = arc
    const color = arc.color || ARC_COLORS[type] || ARC_COLORS.default

    if (!isFinite(fromLon) || !isFinite(fromLat) || !isFinite(toLon) || !isFinite(toLat)) continue
    const dist = distanceKm(fromLon, fromLat, toLon, toLat)
    if (dist < 50) continue

    // Scale arc altitude by distance (50km→10km alt, 5000km→500km alt)
    const maxAlt = Math.min(Math.max(dist * 80, 10000), 500000)
    const allPositions = greatCirclePoints(fromLon, fromLat, toLon, toLat, 60, maxAlt)
    const cesiumColor = Cesium.Color.fromCssColorString(color)

    // Stagger animation start per arc
    const arcDelay = (i % 20) * 150

    // Animated arc using CallbackProperty for growth effect
    const arcStartTime = startTime + arcDelay
    const growDuration = 2000 // 2 seconds to grow

    const entity = ds.entities.add({
      polyline: {
        positions: new Cesium.CallbackProperty(() => {
          const elapsed = Date.now() - arcStartTime
          if (elapsed < 0) return [allPositions[0], allPositions[0]]
          const progress = Math.min(elapsed / growDuration, 1.0)
          // Ease-out cubic
          const eased = 1 - Math.pow(1 - progress, 3)
          const idx = Math.round(eased * (allPositions.length - 1))
          return allPositions.slice(0, Math.max(idx + 1, 2))
        }, false),
        width: width + 1,
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.35,
          taperPower: 0.6,
          color: cesiumColor.withAlpha(0.85),
        }),
        clampToGround: false,
      },
    })

    if (label) {
      entity._tooltipData = {
        title: label,
        rows: {
          Distance: Math.round(dist) + ' km',
          Type: type.replace(/_/g, ' '),
        },
      }
    }

    // Trail effect: faded secondary polyline
    ds.entities.add({
      polyline: {
        positions: allPositions,
        width: Math.max(width - 1, 1),
        material: new Cesium.PolylineGlowMaterialProperty({
          glowPower: 0.15,
          taperPower: 0.9,
          color: cesiumColor.withAlpha(0.2),
        }),
        clampToGround: false,
      },
    })

    // Impact flash: pulsing ellipse at target
    const impactColor = cesiumColor.withAlpha(0.4)
    const impactStart = arcStartTime + growDuration
    const impactDuration = 3000

    ds.entities.add({
      position: Cesium.Cartesian3.fromDegrees(toLon, toLat),
      ellipse: {
        semiMinorAxis: new Cesium.CallbackProperty(() => {
          const elapsed = Date.now() - impactStart
          if (elapsed < 0) return 0
          const progress = Math.min(elapsed / impactDuration, 1.0)
          return progress * 80000 // Expand to 80km radius
        }, false),
        semiMajorAxis: new Cesium.CallbackProperty(() => {
          const elapsed = Date.now() - impactStart
          if (elapsed < 0) return 0
          const progress = Math.min(elapsed / impactDuration, 1.0)
          return progress * 80000
        }, false),
        material: new Cesium.ColorMaterialProperty(
          new Cesium.CallbackProperty(() => {
            const elapsed = Date.now() - impactStart
            if (elapsed < 0) return Cesium.Color.TRANSPARENT
            const progress = Math.min(elapsed / impactDuration, 1.0)
            // Fade out
            const alpha = 0.5 * (1 - progress)
            return cesiumColor.withAlpha(alpha)
          }, false)
        ),
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      },
    })
  }
}

/**
 * Extract arc data from missile/strike events that have origin info.
 * @param {Array} items - Raw API items from missile_tests or conflicts layer
 * @returns {Array} arcData entries
 */
export function extractArcsFromEvents(items) {
  const arcs = []
  for (const item of items) {
    const props = item.properties || item
    const toLon = props.longitude ?? props.lon
    const toLat = props.latitude ?? props.lat
    const fromLon = props.origin_longitude ?? props.from_lon ?? props.source_lon
    const fromLat = props.origin_latitude ?? props.from_lat ?? props.source_lat

    if (isFinite(fromLon) && isFinite(fromLat) && isFinite(toLon) && isFinite(toLat)) {
      const etype = (props.type || 'default').toLowerCase()
      const confidence = props.origin_confidence || ''
      const severity = (props.severity || '').toLowerCase()

      // Color by type
      const color = ARC_COLORS[etype] || (
        severity === 'critical' ? '#ff0000'
        : severity === 'high' ? '#ef4444'
        : '#f97316'
      )

      arcs.push({
        fromLon, fromLat, toLon, toLat,
        color,
        type: etype,
        label: props.title || props.name || 'Attack Vector',
        width: confidence === 'confirmed' ? 4 : 3,
      })
    }
  }
  return arcs
}

/**
 * Build cyber attack arcs from threat_intel data.
 */
export function extractCyberArcs(items) {
  const arcs = []
  for (const item of items) {
    const props = item.properties || item
    const lon = props.longitude ?? props.lon
    const lat = props.latitude ?? props.lat
    if (!isFinite(lon) || !isFinite(lat)) continue

    const severity = (props.severity || 'low').toLowerCase()
    if (severity === 'low') continue

    const color = severity === 'critical' ? '#ff0000'
      : severity === 'high' ? '#ef4444'
      : '#f97316'

    const trailLen = 3 + Math.random() * 5
    arcs.push({
      fromLon: lon + trailLen * (Math.random() - 0.5),
      fromLat: lat + trailLen * (Math.random() - 0.5),
      toLon: lon,
      toLat: lat,
      color,
      type: 'cyber',
      label: (props.title || 'Threat') + ' - ' + (props.source || 'Intel'),
      width: 2,
    })
  }
  return arcs
}
