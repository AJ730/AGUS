import React, { useState } from 'react'

const FREQ_PRESETS = [
  { label: 'MIL HF', freq: '4000-30000', desc: 'Military HF (4-30 MHz)' },
  { label: 'AVIATION', freq: '108000-137000', desc: 'Aviation (108-137 MHz)' },
  { label: 'MARITIME', freq: '156000-162000', desc: 'Maritime VHF (156-162 MHz)' },
  { label: 'EMERG', freq: '121500', desc: 'Emergency 121.5 MHz' },
  { label: 'MIL UHF', freq: '243000', desc: 'Military Emergency 243 MHz' },
  { label: 'ADS-B', freq: '1090000', desc: 'ADS-B 1090 MHz' },
]

const RadioPanel = React.memo(function RadioPanel({ data, onClose }) {
  const [activePreset, setActivePreset] = useState(null)

  if (!data) return null

  const sdrUrl = data.url || data.stream_url || ''
  const name = data.name || 'SDR Receiver'

  return (
    <div className={'radio-panel' + (data ? ' open' : '')}>
      <div className="panel-header">
        <h2>RADIO / SDR</h2>
        <button className="panel-close" onClick={onClose}>&times;</button>
      </div>

      {/* SDR Info */}
      <div className="radio-info">
        <div className="radio-name">
          {name}
        </div>
        {data.location && (
          <div className="radio-location">{data.location}</div>
        )}
        {data.frequency_range && (
          <div className="radio-freq">
            FREQ: {data.frequency_range}
          </div>
        )}
        {data.users_max && (
          <div className="radio-users">
            USERS: {data.users || 0}/{data.users_max}
          </div>
        )}
      </div>

      {/* KiwiSDR Web Interface Embed */}
      {sdrUrl ? (
        <iframe
          className="radio-embed"
          src={sdrUrl}
          title={name}
          allow="autoplay; microphone"
        />
      ) : (
        <div className="radio-empty">
          No web interface available for this receiver.
          <br />
          <button
            className="track-btn radio-open-btn"
            onClick={() => sdrUrl && window.open(sdrUrl, '_blank')}
          >
            OPEN IN NEW TAB
          </button>
        </div>
      )}

      {/* Frequency Presets */}
      <div className="freq-presets">
        {FREQ_PRESETS.map(preset => (
          <button
            key={preset.label}
            className={'freq-btn' + (activePreset === preset.label ? ' active' : '')}
            onClick={() => setActivePreset(preset.label)}
            title={preset.desc}
          >
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  )
})

export default RadioPanel
