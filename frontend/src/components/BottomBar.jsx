import React from 'react'
import { LAYERS } from '../config/layers'
import { fmt } from '../utils/helpers'

const BottomBar = React.memo(function BottomBar({ cameraAlt }) {
  const feedCount = Object.keys(LAYERS).length

  return (
    <footer className="bottombar">
      <span className="status-dot live" /> LIVE
      <span className="bottombar-sep">|</span>
      <span>Sources: {feedCount} OSINT feeds</span>
      <span className="bottombar-sep">|</span>
      <span>Camera: {fmt(cameraAlt)} km</span>
    </footer>
  )
})
export default BottomBar
