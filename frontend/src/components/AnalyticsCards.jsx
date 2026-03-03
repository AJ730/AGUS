import React from 'react'
import { fmt } from '../utils/helpers'

const ANALYTICS_METRICS = [
  { key: 'flights',     label: 'Flights',     color: '#fbbf24' },
  { key: 'conflicts',   label: 'Conflicts',   color: '#ef4444' },
  { key: 'earthquakes', label: 'Earthquakes', color: '#eab308' },
  { key: 'fires',       label: 'Fires',       color: '#f97316' },
  { key: 'news',        label: 'News',        color: '#10b981' },
  { key: 'threat_intel', label: 'Threats',   color: '#f43f5e' },
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
