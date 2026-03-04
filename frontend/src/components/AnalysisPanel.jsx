import React, { useState } from 'react'

const AnalysisPanel = React.memo(function AnalysisPanel({ data, onClose, onFlyTo }) {
  const [terminalMode, setTerminalMode] = useState(false)

  if (!data) return null

  const predictions = data.predictions || []
  const sources = data.sources || []

  return (
    <div className={'analysis-panel' + (data ? ' open' : '')}>
      <div className="panel-header">
        <h2>INTEL ANALYSIS</h2>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            className="map-style-btn"
            style={terminalMode ? { color: '#33ff33', background: 'rgba(51, 255, 51, 0.1)' } : {}}
            onClick={() => setTerminalMode(!terminalMode)}
            title="Terminal mode"
          >
            {'>_'}
          </button>
          <button className="panel-close" onClick={onClose}>&times;</button>
        </div>
      </div>

      <div className={'analysis-body' + (terminalMode ? ' terminal-mode' : '')}>
        {/* Loading */}
        {data.loading && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <div className="loading-spinner" style={{ margin: '0 auto 16px' }} />
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', letterSpacing: '2px', color: 'var(--text-muted)' }}>
              ANALYZING INTELLIGENCE DATA...
            </div>
          </div>
        )}

        {/* Threat Level */}
        {data.threat_level && (
          <div className="analysis-section">
            <div className="analysis-section-header">THREAT ASSESSMENT</div>
            <span className={`analysis-threat-level ${data.threat_level.toLowerCase()}`}>
              {data.threat_level}
            </span>
          </div>
        )}

        {/* Situation Report / Briefing */}
        {data.briefing && (
          <div className="analysis-section">
            <div className="analysis-section-header">SITUATION REPORT</div>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
              {data.briefing}
            </div>
          </div>
        )}

        {/* Satellite Intelligence */}
        {data.satellite_intel && (
          <div className="analysis-section">
            <div className="analysis-section-header">SATELLITE INTELLIGENCE</div>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
              {data.satellite_intel}
            </div>
          </div>
        )}

        {/* Predictions */}
        {predictions.length > 0 && (
          <div className="analysis-section">
            <div className="analysis-section-header">PREDICTIONS</div>
            {predictions.map((pred, i) => (
              <div
                key={i}
                className="analysis-prediction"
                onClick={() => pred.lon && pred.lat && onFlyTo && onFlyTo(pred.lon, pred.lat)}
                title={pred.lon ? 'Click to fly to location' : ''}
              >
                <div style={{ fontSize: '13px', marginBottom: '4px' }}>{pred.text || pred}</div>
                {pred.confidence && (
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Confidence: {pred.confidence}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Sources */}
        {sources.length > 0 && (
          <div className="analysis-section">
            <div className="analysis-section-header">SOURCES</div>
            {sources.map((src, i) => (
              <div key={i} style={{ fontSize: '12px', color: 'var(--text-secondary)', padding: '2px 0' }}>
                [{i + 1}] {src}
              </div>
            ))}
          </div>
        )}

        {/* No data fallback */}
        {!data.loading && !data.briefing && !data.threat_level && (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
            Configure AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY<br />
            environment variables to enable AI analysis.
          </div>
        )}
      </div>
    </div>
  )
})

export default AnalysisPanel
