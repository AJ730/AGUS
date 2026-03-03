import React, { useMemo } from 'react'
import { groupLayers } from '../config/layers'
import { fmt } from '../utils/helpers'

const Sidebar = React.memo(function Sidebar({ layers, layerState, onToggle, collapsedGroups, onToggleGroup, isOpen }) {
  const layerGroups = useMemo(() => groupLayers(layers), [layers])

  return (
    <aside className={'sidebar' + (isOpen ? ' open' : '')}>
      <div className="sidebar-scroll">
        {Object.entries(layerGroups).map(([group, items]) => (
          <div key={group} className="layer-group">
            <div className="group-header" onClick={() => onToggleGroup(group)}>
              <span>{collapsedGroups[group] ? '\u25b6' : '\u25bc'}</span>
              <span>{group.toUpperCase()}</span>
            </div>
            {!collapsedGroups[group] && items.map(layer => (
              <div key={layer.key} className={'layer-card' + (layerState[layer.key].visible ? ' active' : '')}>
                <div className="layer-info" onClick={() => onToggle(layer.key)}>
                  <span className="layer-dot" style={{ background: layer.color }} />
                  <span className="layer-name">{layer.label}</span>
                  <span className="layer-count">{fmt(layerState[layer.key].count)}</span>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={layerState[layer.key].visible} onChange={() => onToggle(layer.key)} />
                  <span className="toggle-slider" />
                </label>
              </div>
            ))}
          </div>
        ))}
      </div>
    </aside>
  )
})

export default Sidebar
