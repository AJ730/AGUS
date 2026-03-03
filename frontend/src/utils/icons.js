// Canvas-drawn icons for OSINT layer billboards.
// Same pattern as airplane.js — cached data URL PNGs, no external files.

// ---------- Shared helpers ----------
function makeCanvas(size) {
  const c = document.createElement('canvas')
  c.width = size; c.height = size
  return [c, c.getContext('2d'), size / 2, size / 32]
}

function applyShadow(ctx, scale) {
  ctx.shadowColor = 'rgba(0,0,0,0.5)'
  ctx.shadowBlur = 3 * scale
  ctx.shadowOffsetX = 1 * scale
  ctx.shadowOffsetY = 1 * scale
}

function clearShadow(ctx) { ctx.shadowColor = 'transparent' }

// ---------- Per-icon caches ----------
const _caches = {}
function cached(ns, color, size, drawFn) {
  if (!_caches[ns]) _caches[ns] = {}
  const key = color + size
  if (_caches[ns][key]) return _caches[ns][key]
  const [canvas, ctx, cx, s] = makeCanvas(size)
  ctx.clearRect(0, 0, size, size)
  drawFn(ctx, cx, cx, s, size, color)
  _caches[ns][key] = canvas.toDataURL('image/png')
  return _caches[ns][key]
}

// ==================== 1. CARRIER (warship top-down) ====================
export function getCarrierIcon(color = '#3b82f6', size = 32) {
  return cached('carrier', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.6)'
    ctx.lineWidth = 0.8 * s
    // Hull — elongated diamond/ship shape
    ctx.beginPath()
    ctx.moveTo(cx, cy - 14 * s)           // bow
    ctx.lineTo(cx - 5 * s, cy - 6 * s)
    ctx.lineTo(cx - 5 * s, cy + 10 * s)
    ctx.lineTo(cx - 3 * s, cy + 13 * s)   // stern port
    ctx.lineTo(cx + 3 * s, cy + 13 * s)   // stern starboard
    ctx.lineTo(cx + 5 * s, cy + 10 * s)
    ctx.lineTo(cx + 5 * s, cy - 6 * s)
    ctx.closePath()
    ctx.fill(); ctx.stroke()
    clearShadow(ctx)
    // Flight deck line
    ctx.strokeStyle = 'rgba(255,255,255,0.35)'
    ctx.lineWidth = 1.5 * s
    ctx.beginPath()
    ctx.moveTo(cx - 3 * s, cy - 4 * s)
    ctx.lineTo(cx + 3 * s, cy + 8 * s)
    ctx.stroke()
    // Island superstructure
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.fillRect(cx + 2 * s, cy - 2 * s, 2.5 * s, 5 * s)
  })
}

// ==================== 2. VESSEL (small ship) ====================
export function getVesselIcon(color = '#3b82f6', size = 32) {
  return cached('vessel', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.6)'
    ctx.lineWidth = 0.7 * s
    // Simple boat hull
    ctx.beginPath()
    ctx.moveTo(cx, cy - 12 * s)           // bow
    ctx.lineTo(cx - 4 * s, cy - 3 * s)
    ctx.lineTo(cx - 4 * s, cy + 8 * s)
    ctx.lineTo(cx - 2 * s, cy + 11 * s)
    ctx.lineTo(cx + 2 * s, cy + 11 * s)
    ctx.lineTo(cx + 4 * s, cy + 8 * s)
    ctx.lineTo(cx + 4 * s, cy - 3 * s)
    ctx.closePath()
    ctx.fill(); ctx.stroke()
    clearShadow(ctx)
    // Cabin
    ctx.fillStyle = 'rgba(255,255,255,0.25)'
    ctx.fillRect(cx - 2 * s, cy - 1 * s, 4 * s, 4 * s)
  })
}

// ==================== 3. SUBMARINE ====================
export function getSubmarineIcon(color = '#0ea5e9', size = 32) {
  return cached('submarine', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.6)'
    ctx.lineWidth = 0.8 * s
    // Sub body — horizontal ellipse rotated vertical
    ctx.beginPath()
    ctx.ellipse(cx, cy + 1 * s, 4 * s, 13 * s, 0, 0, Math.PI * 2)
    ctx.fill(); ctx.stroke()
    clearShadow(ctx)
    // Conning tower
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.5)'
    ctx.lineWidth = 0.6 * s
    ctx.beginPath()
    ctx.roundRect(cx - 1.5 * s, cy - 5 * s, 3 * s, 5 * s, 1 * s)
    ctx.fill(); ctx.stroke()
    // Periscope
    ctx.strokeStyle = 'rgba(255,255,255,0.4)'
    ctx.lineWidth = 0.8 * s
    ctx.beginPath()
    ctx.moveTo(cx, cy - 5 * s)
    ctx.lineTo(cx, cy - 8 * s)
    ctx.stroke()
    // Tail fins
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.moveTo(cx - 1 * s, cy + 12 * s)
    ctx.lineTo(cx - 5 * s, cy + 14 * s)
    ctx.lineTo(cx - 1 * s, cy + 14 * s)
    ctx.closePath()
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(cx + 1 * s, cy + 12 * s)
    ctx.lineTo(cx + 5 * s, cy + 14 * s)
    ctx.lineTo(cx + 1 * s, cy + 14 * s)
    ctx.closePath()
    ctx.fill()
  })
}

// ==================== 4. MILITARY BASE (star badge) ====================
export function getMilitaryBaseIcon(color = '#16a34a', size = 32) {
  return cached('milbase', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.6)'
    ctx.lineWidth = 0.8 * s
    // 5-pointed star
    ctx.beginPath()
    for (let i = 0; i < 5; i++) {
      const outerAngle = (i * 72 - 90) * Math.PI / 180
      const innerAngle = ((i * 72 + 36) - 90) * Math.PI / 180
      const outerR = 13 * s, innerR = 6 * s
      if (i === 0) ctx.moveTo(cx + Math.cos(outerAngle) * outerR, cy + Math.sin(outerAngle) * outerR)
      else ctx.lineTo(cx + Math.cos(outerAngle) * outerR, cy + Math.sin(outerAngle) * outerR)
      ctx.lineTo(cx + Math.cos(innerAngle) * innerR, cy + Math.sin(innerAngle) * innerR)
    }
    ctx.closePath()
    ctx.fill(); ctx.stroke()
    clearShadow(ctx)
    // Center dot
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.beginPath()
    ctx.arc(cx, cy, 3 * s, 0, Math.PI * 2)
    ctx.fill()
  })
}

// ==================== 5. SATELLITE ====================
export function getSatelliteIcon(color = '#e0e0e0', size = 32) {
  return cached('satellite', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.5)'
    ctx.lineWidth = 0.7 * s
    // Central body
    ctx.beginPath()
    ctx.roundRect(cx - 3 * s, cy - 3 * s, 6 * s, 6 * s, 1 * s)
    ctx.fill(); ctx.stroke()
    clearShadow(ctx)
    // Left solar panel
    ctx.fillStyle = '#3b82f6'
    ctx.strokeStyle = 'rgba(0,0,0,0.4)'
    ctx.lineWidth = 0.5 * s
    ctx.fillRect(cx - 14 * s, cy - 4 * s, 10 * s, 8 * s)
    ctx.strokeRect(cx - 14 * s, cy - 4 * s, 10 * s, 8 * s)
    // Panel grid lines left
    ctx.strokeStyle = 'rgba(255,255,255,0.2)'
    ctx.lineWidth = 0.3 * s
    ctx.beginPath()
    ctx.moveTo(cx - 14 * s, cy); ctx.lineTo(cx - 4 * s, cy)
    ctx.moveTo(cx - 9 * s, cy - 4 * s); ctx.lineTo(cx - 9 * s, cy + 4 * s)
    ctx.stroke()
    // Right solar panel
    ctx.fillStyle = '#3b82f6'
    ctx.strokeStyle = 'rgba(0,0,0,0.4)'
    ctx.lineWidth = 0.5 * s
    ctx.fillRect(cx + 4 * s, cy - 4 * s, 10 * s, 8 * s)
    ctx.strokeRect(cx + 4 * s, cy - 4 * s, 10 * s, 8 * s)
    // Panel grid lines right
    ctx.strokeStyle = 'rgba(255,255,255,0.2)'
    ctx.lineWidth = 0.3 * s
    ctx.beginPath()
    ctx.moveTo(cx + 4 * s, cy); ctx.lineTo(cx + 14 * s, cy)
    ctx.moveTo(cx + 9 * s, cy - 4 * s); ctx.lineTo(cx + 9 * s, cy + 4 * s)
    ctx.stroke()
    // Antenna dot
    ctx.fillStyle = '#fbbf24'
    ctx.beginPath()
    ctx.arc(cx, cy, 1.5 * s, 0, Math.PI * 2)
    ctx.fill()
  })
}

// ==================== 6. NUCLEAR (radiation trefoil) ====================
export function getNuclearIcon(color = '#84cc16', size = 32) {
  return cached('nuclear', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    // Draw 3 trefoil blades
    for (let i = 0; i < 3; i++) {
      const angle = (i * 120 - 90) * Math.PI / 180
      ctx.beginPath()
      ctx.arc(cx, cy, 11 * s, angle - 0.45, angle + 0.45)
      ctx.lineTo(cx + Math.cos(angle) * 4 * s, cy + Math.sin(angle) * 4 * s)
      ctx.closePath()
      ctx.fill()
    }
    clearShadow(ctx)
    // Center circle
    ctx.fillStyle = 'rgba(0,0,0,0.7)'
    ctx.beginPath()
    ctx.arc(cx, cy, 3 * s, 0, Math.PI * 2)
    ctx.fill()
    // Inner ring
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(cx, cy, 1.8 * s, 0, Math.PI * 2)
    ctx.fill()
  })
}

// ==================== 7. CCTV (camera) ====================
export function getCctvIcon(color = '#22c55e', size = 32) {
  return cached('cctv', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.6)'
    ctx.lineWidth = 0.7 * s
    // Camera body
    ctx.beginPath()
    ctx.roundRect(cx - 8 * s, cy - 5 * s, 13 * s, 10 * s, 2 * s)
    ctx.fill(); ctx.stroke()
    clearShadow(ctx)
    // Lens/viewfinder triangle
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.5)'
    ctx.beginPath()
    ctx.moveTo(cx + 5 * s, cy - 4 * s)
    ctx.lineTo(cx + 12 * s, cy - 7 * s)
    ctx.lineTo(cx + 12 * s, cy + 7 * s)
    ctx.lineTo(cx + 5 * s, cy + 4 * s)
    ctx.closePath()
    ctx.fill(); ctx.stroke()
    // Lens circle
    ctx.fillStyle = 'rgba(0,0,0,0.4)'
    ctx.beginPath()
    ctx.arc(cx - 1.5 * s, cy, 3 * s, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.beginPath()
    ctx.arc(cx - 2.5 * s, cy - 1 * s, 1 * s, 0, Math.PI * 2)
    ctx.fill()
    // Mount arm
    ctx.strokeStyle = 'rgba(255,255,255,0.2)'
    ctx.lineWidth = 1.5 * s
    ctx.beginPath()
    ctx.moveTo(cx - 2 * s, cy + 5 * s)
    ctx.lineTo(cx - 2 * s, cy + 12 * s)
    ctx.stroke()
  })
}

// ==================== 8. PIRACY (skull & crossbones) ====================
export function getPiracyIcon(color = '#1e293b', size = 32) {
  return cached('piracy', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    // Dark background circle
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(cx, cy, 14 * s, 0, Math.PI * 2)
    ctx.fill()
    clearShadow(ctx)
    // Skull
    ctx.fillStyle = '#ffffff'
    ctx.beginPath()
    ctx.ellipse(cx, cy - 3 * s, 7 * s, 8 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    // Jaw
    ctx.beginPath()
    ctx.ellipse(cx, cy + 3 * s, 5 * s, 3.5 * s, 0, 0, Math.PI)
    ctx.fill()
    // Eye sockets
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.ellipse(cx - 3 * s, cy - 4 * s, 2.2 * s, 2.5 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.beginPath()
    ctx.ellipse(cx + 3 * s, cy - 4 * s, 2.2 * s, 2.5 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    // Nose
    ctx.beginPath()
    ctx.moveTo(cx, cy - 1 * s)
    ctx.lineTo(cx - 1.2 * s, cy + 1 * s)
    ctx.lineTo(cx + 1.2 * s, cy + 1 * s)
    ctx.closePath()
    ctx.fill()
    // Crossbones
    ctx.strokeStyle = '#ffffff'
    ctx.lineWidth = 2 * s
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(cx - 10 * s, cy + 8 * s)
    ctx.lineTo(cx + 10 * s, cy + 14 * s)
    ctx.moveTo(cx + 10 * s, cy + 8 * s)
    ctx.lineTo(cx - 10 * s, cy + 14 * s)
    ctx.stroke()
  })
}

// ==================== 9. TERRORISM (warning triangle) ====================
export function getTerrorismIcon(color = '#b91c1c', size = 32) {
  return cached('terrorism', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.6)'
    ctx.lineWidth = 0.8 * s
    // Triangle
    ctx.beginPath()
    ctx.moveTo(cx, cy - 13 * s)
    ctx.lineTo(cx - 13 * s, cy + 11 * s)
    ctx.lineTo(cx + 13 * s, cy + 11 * s)
    ctx.closePath()
    ctx.fill(); ctx.stroke()
    clearShadow(ctx)
    // Exclamation mark
    ctx.fillStyle = '#ffffff'
    ctx.font = `bold ${16 * s}px sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText('!', cx, cy + 2 * s)
  })
}

// ==================== 10. EARTHQUAKE (seismic waves) ====================
export function getEarthquakeIcon(color = '#ffd700', size = 32) {
  return cached('earthquake', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    // Center dot
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(cx, cy, 3.5 * s, 0, Math.PI * 2)
    ctx.fill()
    clearShadow(ctx)
    // Concentric wave arcs
    ctx.strokeStyle = color
    ctx.lineWidth = 1.2 * s
    for (let r = 7; r <= 13; r += 3) {
      ctx.globalAlpha = 1 - (r - 7) * 0.12
      ctx.beginPath()
      ctx.arc(cx, cy, r * s, -Math.PI * 0.7, -Math.PI * 0.3)
      ctx.stroke()
      ctx.beginPath()
      ctx.arc(cx, cy, r * s, Math.PI * 0.3, Math.PI * 0.7)
      ctx.stroke()
    }
    ctx.globalAlpha = 1
  })
}

// ==================== 11. FIRE (flame) ====================
export function getFireIcon(color = '#f97316', size = 32) {
  return cached('fire', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    // Outer flame
    const grd = ctx.createRadialGradient(cx, cy + 4 * s, 2 * s, cx, cy + 4 * s, 14 * s)
    grd.addColorStop(0, '#fbbf24')
    grd.addColorStop(0.5, color)
    grd.addColorStop(1, '#dc2626')
    ctx.fillStyle = grd
    ctx.beginPath()
    ctx.moveTo(cx, cy - 14 * s)
    ctx.bezierCurveTo(cx - 3 * s, cy - 8 * s, cx - 10 * s, cy - 2 * s, cx - 8 * s, cy + 6 * s)
    ctx.bezierCurveTo(cx - 7 * s, cy + 12 * s, cx - 3 * s, cy + 14 * s, cx, cy + 13 * s)
    ctx.bezierCurveTo(cx + 3 * s, cy + 14 * s, cx + 7 * s, cy + 12 * s, cx + 8 * s, cy + 6 * s)
    ctx.bezierCurveTo(cx + 10 * s, cy - 2 * s, cx + 3 * s, cy - 8 * s, cx, cy - 14 * s)
    ctx.fill()
    clearShadow(ctx)
    // Inner flame
    ctx.fillStyle = '#fde68a'
    ctx.beginPath()
    ctx.moveTo(cx, cy - 4 * s)
    ctx.bezierCurveTo(cx - 1.5 * s, cy, cx - 4 * s, cy + 4 * s, cx - 3 * s, cy + 8 * s)
    ctx.bezierCurveTo(cx - 2 * s, cy + 11 * s, cx + 2 * s, cy + 11 * s, cx + 3 * s, cy + 8 * s)
    ctx.bezierCurveTo(cx + 4 * s, cy + 4 * s, cx + 1.5 * s, cy, cx, cy - 4 * s)
    ctx.fill()
  })
}

// ==================== 12. WEATHER ALERT (storm cloud + lightning) ====================
export function getWeatherAlertIcon(color = '#a855f7', size = 32) {
  return cached('weather', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    // Cloud body (overlapping circles)
    ctx.beginPath()
    ctx.arc(cx - 4 * s, cy - 2 * s, 6 * s, 0, Math.PI * 2)
    ctx.arc(cx + 3 * s, cy - 3 * s, 5 * s, 0, Math.PI * 2)
    ctx.arc(cx + 7 * s, cy, 4 * s, 0, Math.PI * 2)
    ctx.arc(cx - 7 * s, cy, 4 * s, 0, Math.PI * 2)
    ctx.arc(cx, cy + 1 * s, 5 * s, 0, Math.PI * 2)
    ctx.fill()
    clearShadow(ctx)
    // Lightning bolt
    ctx.fillStyle = '#fbbf24'
    ctx.beginPath()
    ctx.moveTo(cx + 1 * s, cy + 2 * s)
    ctx.lineTo(cx - 3 * s, cy + 8 * s)
    ctx.lineTo(cx, cy + 7 * s)
    ctx.lineTo(cx - 2 * s, cy + 14 * s)
    ctx.lineTo(cx + 4 * s, cy + 6 * s)
    ctx.lineTo(cx + 1 * s, cy + 7 * s)
    ctx.lineTo(cx + 4 * s, cy + 2 * s)
    ctx.closePath()
    ctx.fill()
  })
}

// ==================== 13. REFUGEE (people group) ====================
export function getRefugeeIcon(color = '#06b6d4', size = 32) {
  return cached('refugee', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    // Left person — head
    ctx.beginPath()
    ctx.arc(cx - 5 * s, cy - 8 * s, 3.5 * s, 0, Math.PI * 2)
    ctx.fill()
    // Left person — body
    ctx.beginPath()
    ctx.ellipse(cx - 5 * s, cy + 2 * s, 4 * s, 8 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    // Right person — head
    ctx.beginPath()
    ctx.arc(cx + 5 * s, cy - 8 * s, 3.5 * s, 0, Math.PI * 2)
    ctx.fill()
    // Right person — body
    ctx.beginPath()
    ctx.ellipse(cx + 5 * s, cy + 2 * s, 4 * s, 8 * s, 0, 0, Math.PI * 2)
    ctx.fill()
    clearShadow(ctx)
    // Highlight
    ctx.fillStyle = 'rgba(255,255,255,0.2)'
    ctx.beginPath()
    ctx.arc(cx - 5.5 * s, cy - 9 * s, 1.5 * s, 0, Math.PI * 2)
    ctx.arc(cx + 4.5 * s, cy - 9 * s, 1.5 * s, 0, Math.PI * 2)
    ctx.fill()
  })
}

// ==================== 14. CYBER (shield with lock) ====================
export function getCyberIcon(color = '#8b5cf6', size = 32) {
  return cached('cyber', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.6)'
    ctx.lineWidth = 0.8 * s
    // Shield shape
    ctx.beginPath()
    ctx.moveTo(cx, cy - 13 * s)
    ctx.lineTo(cx - 11 * s, cy - 7 * s)
    ctx.lineTo(cx - 10 * s, cy + 3 * s)
    ctx.bezierCurveTo(cx - 8 * s, cy + 10 * s, cx, cy + 14 * s, cx, cy + 14 * s)
    ctx.bezierCurveTo(cx, cy + 14 * s, cx + 8 * s, cy + 10 * s, cx + 10 * s, cy + 3 * s)
    ctx.lineTo(cx + 11 * s, cy - 7 * s)
    ctx.closePath()
    ctx.fill(); ctx.stroke()
    clearShadow(ctx)
    // Lock body
    ctx.fillStyle = 'rgba(255,255,255,0.85)'
    ctx.fillRect(cx - 4 * s, cy - 1 * s, 8 * s, 7 * s)
    // Lock shackle
    ctx.strokeStyle = 'rgba(255,255,255,0.85)'
    ctx.lineWidth = 1.5 * s
    ctx.beginPath()
    ctx.arc(cx, cy - 2 * s, 3 * s, Math.PI, 0)
    ctx.stroke()
    // Keyhole
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(cx, cy + 2 * s, 1.5 * s, 0, Math.PI * 2)
    ctx.fill()
  })
}

// ==================== 15. THREAT INTEL (crosshair/target reticle) ====================
export function getThreatIntelIcon(color = '#f43f5e', size = 32) {
  return cached('threatintel', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.strokeStyle = color
    ctx.lineWidth = 1.5 * s
    // Outer circle
    ctx.beginPath()
    ctx.arc(cx, cy, 12 * s, 0, Math.PI * 2)
    ctx.stroke()
    // Inner circle
    ctx.beginPath()
    ctx.arc(cx, cy, 6 * s, 0, Math.PI * 2)
    ctx.stroke()
    clearShadow(ctx)
    // Crosshair lines
    ctx.lineWidth = 1.2 * s
    ctx.beginPath()
    ctx.moveTo(cx, cy - 14 * s); ctx.lineTo(cx, cy - 3 * s)
    ctx.moveTo(cx, cy + 3 * s); ctx.lineTo(cx, cy + 14 * s)
    ctx.moveTo(cx - 14 * s, cy); ctx.lineTo(cx - 3 * s, cy)
    ctx.moveTo(cx + 3 * s, cy); ctx.lineTo(cx + 14 * s, cy)
    ctx.stroke()
    // Center dot
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(cx, cy, 2 * s, 0, Math.PI * 2)
    ctx.fill()
  })
}

// ==================== 16. SIGNALS/SDR (radio antenna with waves) ====================
export function getSignalsIcon(color = '#a78bfa', size = 32) {
  return cached('signals', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.strokeStyle = color
    ctx.fillStyle = color
    ctx.lineWidth = 1.5 * s
    // Antenna mast
    ctx.beginPath()
    ctx.moveTo(cx, cy + 14 * s)
    ctx.lineTo(cx, cy - 6 * s)
    ctx.stroke()
    // Antenna tip
    ctx.beginPath()
    ctx.arc(cx, cy - 7 * s, 2 * s, 0, Math.PI * 2)
    ctx.fill()
    clearShadow(ctx)
    // Wave arcs (left)
    ctx.lineWidth = 1.2 * s
    for (let i = 0; i < 3; i++) {
      const r = (5 + i * 4) * s
      ctx.globalAlpha = 1 - i * 0.25
      ctx.beginPath()
      ctx.arc(cx, cy - 6 * s, r, -Math.PI * 0.8, -Math.PI * 0.2)
      ctx.stroke()
    }
    ctx.globalAlpha = 1
    // Base
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.moveTo(cx - 5 * s, cy + 14 * s)
    ctx.lineTo(cx + 5 * s, cy + 14 * s)
    ctx.lineTo(cx, cy + 10 * s)
    ctx.closePath()
    ctx.fill()
  })
}

// ==================== 17. MILITARY VESSEL (angular warship) ====================
export function getMilitaryVesselIcon(color = '#ef4444', size = 32) {
  return cached('milvessel', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.fillStyle = color
    ctx.strokeStyle = 'rgba(0,0,0,0.6)'
    ctx.lineWidth = 0.8 * s
    // Angular hull
    ctx.beginPath()
    ctx.moveTo(cx, cy - 14 * s)           // bow
    ctx.lineTo(cx - 6 * s, cy - 5 * s)
    ctx.lineTo(cx - 5 * s, cy + 10 * s)
    ctx.lineTo(cx - 3 * s, cy + 13 * s)
    ctx.lineTo(cx + 3 * s, cy + 13 * s)
    ctx.lineTo(cx + 5 * s, cy + 10 * s)
    ctx.lineTo(cx + 6 * s, cy - 5 * s)
    ctx.closePath()
    ctx.fill(); ctx.stroke()
    clearShadow(ctx)
    // Gun turret
    ctx.fillStyle = 'rgba(255,255,255,0.3)'
    ctx.beginPath()
    ctx.arc(cx, cy - 2 * s, 3 * s, 0, Math.PI * 2)
    ctx.fill()
    // Gun barrel
    ctx.strokeStyle = 'rgba(255,255,255,0.4)'
    ctx.lineWidth = 1.5 * s
    ctx.beginPath()
    ctx.moveTo(cx, cy - 2 * s)
    ctx.lineTo(cx, cy - 9 * s)
    ctx.stroke()
    // Superstructure
    ctx.fillStyle = 'rgba(255,255,255,0.2)'
    ctx.fillRect(cx - 2 * s, cy + 2 * s, 4 * s, 5 * s)
  })
}

// ==================== 18. SANCTIONS (ban circle) ====================
export function getSanctionIcon(color = '#d97706', size = 32) {
  return cached('sanction', color, size, (ctx, cx, cy, s) => {
    applyShadow(ctx, s)
    ctx.strokeStyle = color
    ctx.lineWidth = 3 * s
    // Outer circle
    ctx.beginPath()
    ctx.arc(cx, cy, 12 * s, 0, Math.PI * 2)
    ctx.stroke()
    // Diagonal slash
    ctx.beginPath()
    ctx.moveTo(cx - 8.5 * s, cy - 8.5 * s)
    ctx.lineTo(cx + 8.5 * s, cy + 8.5 * s)
    ctx.stroke()
    clearShadow(ctx)
    // Fill circle lightly
    ctx.fillStyle = color.replace(')', ',0.15)').replace('rgb', 'rgba')
    ctx.globalAlpha = 0.15
    ctx.beginPath()
    ctx.arc(cx, cy, 12 * s, 0, Math.PI * 2)
    ctx.fill()
    ctx.globalAlpha = 1
  })
}
