import React, { useCallback, useMemo } from 'react'

const MAX_HOURS = 24
const SLIDER_MAX = 1000 // Higher resolution slider

/**
 * TimelineBar — 4D timeline scrubbing bar.
 * Maps a range slider (0-1000) to -24h → now.
 * Props: onTimeChange(timestamp | null), timelineTs (current ts or null for live)
 */
const TimelineBar = React.memo(function TimelineBar({ onTimeChange, timelineTs }) {
  const isLive = timelineTs === null

  const sliderValue = useMemo(() => {
    if (isLive) return SLIDER_MAX
    const now = Date.now() / 1000
    const hoursAgo = (now - timelineTs) / 3600
    const clamped = Math.max(0, Math.min(MAX_HOURS, hoursAgo))
    return Math.round(SLIDER_MAX * (1 - clamped / MAX_HOURS))
  }, [timelineTs, isLive])

  const timeLabel = useMemo(() => {
    if (isLive) return 'LIVE'
    const d = new Date(timelineTs * 1000)
    return d.toISOString().slice(11, 19) + 'Z'
  }, [timelineTs, isLive])

  const handleSliderChange = useCallback((e) => {
    const val = Number(e.target.value)
    if (val >= SLIDER_MAX) {
      onTimeChange(null) // snap to live
      return
    }
    const hoursAgo = MAX_HOURS * (1 - val / SLIDER_MAX)
    const ts = Date.now() / 1000 - hoursAgo * 3600
    onTimeChange(ts)
  }, [onTimeChange])

  const handleLiveClick = useCallback(() => {
    onTimeChange(null)
  }, [onTimeChange])

  return (
    <div className="timeline-bar">
      <button
        className={'timeline-live-btn' + (isLive ? ' active' : '')}
        onClick={handleLiveClick}
      >
        LIVE
      </button>
      <input
        className="timeline-slider"
        type="range"
        min={0}
        max={SLIDER_MAX}
        value={sliderValue}
        onChange={handleSliderChange}
      />
      <span className="timeline-time">{timeLabel}</span>
      <span className="timeline-range">-{MAX_HOURS}h</span>
    </div>
  )
})

export default TimelineBar
