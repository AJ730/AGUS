import React from 'react'
import { PRESETS } from '../config/layers'
import { fmt } from '../utils/helpers'

const TopBar = React.memo(function TopBar({ onMenuToggle, onFlyToPreset, searchQuery, onSearchChange, onSearch, cameraAlt }) {
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
