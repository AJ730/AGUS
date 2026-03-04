import React, { useCallback } from 'react'
import { PRESETS } from '../config/layers'
import { GIBS_LAYERS } from '../utils/gibsLayers'
import { fmt } from '../utils/helpers'

const TopBar = React.memo(function TopBar({
  onMenuToggle, onFlyToPreset, searchQuery, onSearchChange, onSearch,
  cameraAlt, mapStyle, onMapStyleChange, onAnalyze,
  visualFilter, onVisualFilterChange,
  gibsActive, onGibsToggle,
  trafficOverlay, onTrafficToggle,
}) {
  const toggleGibs = useCallback((key) => {
    onGibsToggle(prev => ({ ...prev, [key]: !prev[key] }))
  }, [onGibsToggle])

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="menu-btn" onClick={onMenuToggle}>&#9776;</button>
        <div className="brand">
          <h1>AGUS</h1>
          <span className="brand-sub">OSINT Intelligence Platform</span>
        </div>
      </div>
      <div className="topbar-center">
        {PRESETS.map(p => (
          <button key={p.name} className="preset-btn" onClick={() => onFlyToPreset(p)}>
            {p.name}
          </button>
        ))}
      </div>
      <div className="topbar-right">
        {/* Visual Filter Toggle */}
        <div className="filter-toggle">
          {[
            { key: 'crt', label: 'CRT', title: 'CRT Monitor' },
            { key: 'nvg', label: 'NVG', title: 'Night Vision' },
            { key: 'flir', label: 'FLIR', title: 'Thermal/FLIR' },
            { key: 'anime', label: 'ANM', title: 'Anime Cel-Shading' },
            { key: 'reticle', label: 'TGT', title: 'Targeting Reticle' },
            { key: 'none', label: 'OFF', title: 'No Filter' },
          ].map(f => (
            <button
              key={f.key}
              className={'filter-btn' + (visualFilter === f.key ? ' active' : '')}
              onClick={() => onVisualFilterChange(f.key)}
              title={f.title}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Map Style Toggle */}
        <div className="map-style-toggle">
          {[
            { key: 'satellite', label: 'SAT' },
            { key: 'hybrid', label: 'HYB' },
            { key: 'dark', label: 'DARK' },
            { key: 'darksat', label: 'NITE' },
            { key: '3d', label: '3D' },
          ].map(s => (
            <button
              key={s.key}
              className={'map-style-btn' + (mapStyle === s.key ? ' active' : '')}
              onClick={() => onMapStyleChange(s.key)}
              title={s.key === 'darksat' ? 'Dark + Nightlights' : s.key === '3d' ? 'Google 3D Tiles' : s.label}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* GIBS + Traffic Overlays */}
        <div className="gibs-toggle">
          {Object.entries(GIBS_LAYERS).map(([key, cfg]) => (
            <button
              key={key}
              className={'gibs-btn' + (gibsActive[key] ? ' active' : '')}
              onClick={() => toggleGibs(key)}
              title={cfg.label}
            >
              {key === 'viirs_thermal' ? 'THM' : key === 'nightlights' ? 'NLT' : key === 'aerosol' ? 'AER' : 'SAT'}
            </button>
          ))}
          <button
            className={'gibs-btn' + (trafficOverlay ? ' active' : '')}
            onClick={() => onTrafficToggle(prev => !prev)}
            title="Google Live Traffic"
          >
            TRF
          </button>
        </div>

        {/* Analyze Region Button */}
        {onAnalyze && (
          <button
            className="analyze-btn"
            onClick={() => onAnalyze({ region: 'Global', layers: ['conflicts', 'missile_tests', 'threat_intel'] })}
          >
            ANALYZE
          </button>
        )}

        <div className="search-box">
          <input
            type="text"
            placeholder="Search location..."
            value={searchQuery}
            onChange={e => onSearchChange(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onSearch()}
          />
          <button onClick={onSearch}>&rarr;</button>
        </div>
        <div className="cam-alt">{fmt(cameraAlt)} km</div>
      </div>
    </header>
  )
})
export default TopBar
