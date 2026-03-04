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
        <div className="analysis-header-actions">
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
          <div className="analysis-loading">
            <div className="loading-spinner analysis-loading-spinner" />
            <div className="analysis-loading-text">
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
            <div className="analysis-preformatted">
              {data.briefing}
            </div>
          </div>
        )}

        {/* Satellite Intelligence */}
        {data.satellite_intel && (
          <div className="analysis-section">
            <div className="analysis-section-header">SATELLITE INTELLIGENCE</div>
            <div className="analysis-preformatted">
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
                <div className="analysis-prediction-text">{pred.text || pred}</div>
                {pred.confidence && (
                  <div className="analysis-prediction-confidence">
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
              <div key={i} className="analysis-source-item">
                [{i + 1}] {src}
              </div>
            ))}
          </div>
        )}

        {/* No data fallback */}
        {!data.loading && !data.briefing && !data.threat_level && (
          <div className="analysis-empty">
            Configure AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY<br />
            environment variables to enable AI analysis.
          </div>
        )}
      </div>
    </div>
  )
})

export default AnalysisPanel
