import React, { useEffect, useRef, useCallback } from 'react'

const API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || ''

// Load Google Maps JS API once (singleton)
let mapsPromise = null
function loadMapsAPI() {
  if (window.google && window.google.maps) return Promise.resolve()
  if (mapsPromise) return mapsPromise
  mapsPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = `https://maps.googleapis.com/maps/api/js?key=${API_KEY}&loading=async`
    script.async = true
    script.onload = resolve
    script.onerror = reject
    document.head.appendChild(script)
  })
  return mapsPromise
}

const StreetViewPanel = React.memo(function StreetViewPanel({ data, onClose }) {
  const containerRef = useRef(null)
  const panoRef = useRef(null)

  useEffect(() => {
    if (!data || !API_KEY) return
    let cancelled = false

    loadMapsAPI().then(() => {
      if (cancelled || !containerRef.current) return
      if (!panoRef.current) {
        panoRef.current = new window.google.maps.StreetViewPanorama(containerRef.current, {
          position: { lat: data.lat, lng: data.lon },
          pov: { heading: data.heading || 0, pitch: 0 },
          zoom: 1,
          addressControl: true,
          showRoadLabels: true,
          motionTracking: false,
        })
      } else {
        panoRef.current.setPosition({ lat: data.lat, lng: data.lon })
        panoRef.current.setPov({ heading: data.heading || 0, pitch: 0 })
      }
    }).catch(() => {})

    return () => { cancelled = true }
  }, [data?.lat, data?.lon, data?.heading])

  // Destroy panorama when panel closes
  useEffect(() => {
    if (!data && panoRef.current) {
      panoRef.current = null
    }
  }, [data])

  // Close on Escape key
  useEffect(() => {
    if (!data) return
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [data, onClose])

  const openInMaps = useCallback(() => {
    if (!data) return
    window.open(`https://www.google.com/maps/@${data.lat},${data.lon},3a,75y,${data.heading || 0}h,90t/data=!3m1!1e1`, '_blank')
  }, [data])

  if (!data) return null

  return (
    <div className="street-view-panel open">
      <div className="sv-overlay-bar">
        <span className="sv-overlay-title">STREET VIEW</span>
        <span className="sv-coord-text">{data.lat.toFixed(5)}, {data.lon.toFixed(5)}</span>
        <div className="sv-header-actions">
          <button className="sv-maps-btn" onClick={openInMaps} title="Open in Google Maps">OPEN IN MAPS</button>
          <button className="sv-close-btn" onClick={onClose} title="Close (Esc)">&times;</button>
        </div>
      </div>
      <div className="sv-panorama" ref={containerRef} />
    </div>
  )
})

export default StreetViewPanel
