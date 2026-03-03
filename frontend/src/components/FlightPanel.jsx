import React from 'react'
import { clamp } from '../utils/helpers'

const FlightPanel = React.memo(function FlightPanel({ flight, onClose, onTrack }) {
  if (!flight) return null

  return (
    <div className="flight-panel open">
      <div className="panel-header">
        <h2>{flight.callsign || 'Unknown'}</h2>
        <button className="panel-close" onClick={onClose}>&times;</button>
      </div>
      <div className="panel-body">
        <div className="panel-badge" data-military={flight.is_military ? 'true' : 'false'}>
          {flight.is_military ? 'MILITARY' : 'CIVILIAN'}
        </div>
        <div className="panel-grid">
          <div className="panel-field">
            <label>Country</label>
            <span>{flight.country || 'Unknown'}</span>
          </div>
          <div className="panel-field">
            <label>ICAO24</label>
            <span style={{fontFamily: 'monospace'}}>{flight.icao24 || 'N/A'}</span>
          </div>
          <div className="panel-field">
            <label>Aircraft</label>
            <span>{flight.aircraft_type || 'N/A'}</span>
          </div>
          <div className="panel-field">
            <label>Registration</label>
            <span>{flight.registration || 'N/A'}</span>
          </div>
          <div className="panel-field">
            <label>Altitude</label>
            <span>{Math.round(flight.altitude || 0).toLocaleString()} m ({Math.round((flight.altitude || 0) * 3.281).toLocaleString()} ft)</span>
          </div>
          <div className="panel-field">
            <label>Speed</label>
            <span>{Math.round(flight.speed || 0)} kts</span>
          </div>
          <div className="panel-field">
            <label>Heading</label>
            <span>{Math.round(flight.heading || 0)}&deg;</span>
          </div>
          <div className="panel-field">
            <label>Vert Rate</label>
            <span>{(flight.vertical_rate || 0) > 0 ? '+' : ''}{(flight.vertical_rate || 0).toFixed(1)} ft/min</span>
          </div>
          <div className="panel-field">
            <label>Squawk</label>
            <span className={flight.squawk_alert ? 'squawk-alert' : ''}>
              {flight.squawk || 'N/A'}
              {flight.squawk_alert ? ' (' + flight.squawk_alert + ')' : ''}
            </span>
          </div>
          <div className="panel-field">
            <label>Route</label>
            <span>{flight.flight_route || 'N/A'}</span>
          </div>
          <div className="panel-field">
            <label>Position</label>
            <span style={{fontFamily: 'monospace', fontSize: '0.75rem'}}>
              {(flight.latitude || 0).toFixed(4)}, {(flight.longitude || 0).toFixed(4)}
            </span>
          </div>
          <div className="panel-field">
            <label>On Ground</label>
            <span>{flight.on_ground ? 'Yes' : 'No'}</span>
          </div>
        </div>
        <div className="altitude-bar">
          <div
            className="altitude-fill"
            style={{ width: clamp((flight.altitude || 0) / 15000 * 100, 0, 100) + '%' }}
          />
        </div>
        <button className="track-btn" onClick={() => onTrack(flight.icao24)}>
          TRACK FLIGHT
        </button>
      </div>
    </div>
  )
})
export default FlightPanel
