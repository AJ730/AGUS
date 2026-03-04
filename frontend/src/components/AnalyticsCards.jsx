import React from 'react'
import { fmt } from '../utils/helpers'

const ANALYTICS_METRICS = [
  { key: 'flights',       label: 'Flights',     color: '#fbbf24' },
  { key: 'conflicts',     label: 'Conflicts',   color: '#ef4444' },
  { key: 'earthquakes',   label: 'Earthquakes', color: '#eab308' },
  { key: 'fires',         label: 'Fires',       color: '#f97316' },
  { key: 'news',          label: 'News',        color: '#10b981' },
  { key: 'telegram_osint', label: 'OSINT',     color: '#0088cc' },
  { key: 'threat_intel',  label: 'Threats',     color: '#f43f5e' },
  { key: 'missile_tests', label: 'Missiles',   color: '#dc2626' },
  { key: 'rocket_alerts', label: 'Alerts',     color: '#ff0000' },
  { key: 'reddit_osint', label: 'Reddit',     color: '#ff4500' },
  { key: 'equipment_losses', label: 'Eq. Loss', color: '#92400e' },
  { key: 'gps_jamming', label: 'GPS Jam',       color: '#e11d48' },
]

const AnalyticsCards = React.memo(function AnalyticsCards({ analytics }) {
  return (
    <div className="analytics-cards">
      {ANALYTICS_METRICS.map(metric => (
        <div key={metric.key} className="stat-card">
          <span className="stat-value" style={{ color: metric.color }}>
            {fmt(analytics[metric.key] || 0)}
          </span>
          <span className="stat-label">{metric.label}</span>
        </div>
      ))}
    </div>
  )
})

export default AnalyticsCards
