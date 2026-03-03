// Canvas-drawn airplane silhouette for flight billboards.
// No external image files required - everything is generated at runtime.

let _airplaneYellow = null
let _airplaneRed = null

function createAirplaneDataURL(color, size = 48) {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')

  // Clear with transparent background
  ctx.clearRect(0, 0, size, size)

  const cx = size / 2
  const cy = size / 2
  const scale = size / 32

  // Drop shadow for depth
  ctx.shadowColor = 'rgba(0,0,0,0.5)'
  ctx.shadowBlur = 3 * scale
  ctx.shadowOffsetX = 1 * scale
  ctx.shadowOffsetY = 1 * scale

  ctx.fillStyle = color
  ctx.strokeStyle = 'rgba(0,0,0,0.6)'
  ctx.lineWidth = 0.8 * scale

  // Fuselage
  ctx.beginPath()
  ctx.moveTo(cx, cy - 14 * scale)              // nose
  ctx.lineTo(cx - 2.5 * scale, cy - 8 * scale)
  ctx.lineTo(cx - 2.5 * scale, cy + 4 * scale)
  ctx.lineTo(cx - 1.5 * scale, cy + 12 * scale)  // tail
  ctx.lineTo(cx + 1.5 * scale, cy + 12 * scale)
  ctx.lineTo(cx + 2.5 * scale, cy + 4 * scale)
  ctx.lineTo(cx + 2.5 * scale, cy - 8 * scale)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()

  // Turn off shadow for wings
  ctx.shadowColor = 'transparent'

  // Left wing
  ctx.beginPath()
  ctx.moveTo(cx - 2.5 * scale, cy - 2 * scale)
  ctx.lineTo(cx - 14 * scale, cy + 3 * scale)
  ctx.lineTo(cx - 14 * scale, cy + 5 * scale)
  ctx.lineTo(cx - 2.5 * scale, cy + 2 * scale)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()

  // Right wing
  ctx.beginPath()
  ctx.moveTo(cx + 2.5 * scale, cy - 2 * scale)
  ctx.lineTo(cx + 14 * scale, cy + 3 * scale)
  ctx.lineTo(cx + 14 * scale, cy + 5 * scale)
  ctx.lineTo(cx + 2.5 * scale, cy + 2 * scale)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()

  // Left tail fin
  ctx.beginPath()
  ctx.moveTo(cx - 1.5 * scale, cy + 8 * scale)
  ctx.lineTo(cx - 7 * scale, cy + 12 * scale)
  ctx.lineTo(cx - 7 * scale, cy + 13 * scale)
  ctx.lineTo(cx - 1.5 * scale, cy + 10 * scale)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()

  // Right tail fin
  ctx.beginPath()
  ctx.moveTo(cx + 1.5 * scale, cy + 8 * scale)
  ctx.lineTo(cx + 7 * scale, cy + 12 * scale)
  ctx.lineTo(cx + 7 * scale, cy + 13 * scale)
  ctx.lineTo(cx + 1.5 * scale, cy + 10 * scale)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()

  // Nose highlight
  ctx.fillStyle = 'rgba(255,255,255,0.3)'
  ctx.beginPath()
  ctx.moveTo(cx, cy - 13 * scale)
  ctx.lineTo(cx - 1 * scale, cy - 8 * scale)
  ctx.lineTo(cx + 1 * scale, cy - 8 * scale)
  ctx.closePath()
  ctx.fill()

  // Return as data URL for reliable GPU rendering
  return canvas.toDataURL('image/png')
}

// Returns a cached data URL string for the airplane billboard.
// Yellow for civilian flights, red for military.
// Using data URLs instead of canvas elements for reliable GPU rendering
// (avoids black box issue on some WebGL/GPU driver combinations).
export function getAirplaneBillboard(isMilitary) {
  if (isMilitary) {
    if (!_airplaneRed) _airplaneRed = createAirplaneDataURL('#ff4444', 48)
    return _airplaneRed
  } else {
    if (!_airplaneYellow) _airplaneYellow = createAirplaneDataURL('#fbbf24', 48)
    return _airplaneYellow
  }
}
