import * as Cesium from 'cesium'

// Escape HTML entities to prevent XSS in tooltip innerHTML
export function escapeHtml(str) {
  if (typeof str !== 'string') return String(str ?? '')
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// Format large numbers for display (e.g. 1500 -> "1.5K")
export function fmt(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

// Clamp a value between min and max
export function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v))
}

// Convert a CSS hex color string to a Cesium Color with optional alpha
export function hexColor(hex, alpha = 1) {
  return Cesium.Color.fromCssColorString(hex).withAlpha(alpha)
}
