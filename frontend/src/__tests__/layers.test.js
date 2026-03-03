import { describe, it, expect } from 'vitest'
import { LAYERS, PRESETS, DEFAULT_VISIBLE_LAYERS, groupLayers } from '../config/layers'

describe('LAYERS configuration', () => {
  it('has exactly 20 layer entries', () => {
    expect(Object.keys(LAYERS)).toHaveLength(20)
  })

  it('every layer has required fields: label, group, color, refreshMs', () => {
    for (const [key, cfg] of Object.entries(LAYERS)) {
      expect(cfg.label, `${key} missing label`).toBeTruthy()
      expect(cfg.group, `${key} missing group`).toBeTruthy()
      expect(cfg.color, `${key} missing color`).toMatch(/^#[0-9a-fA-F]{6}$/)
      expect(cfg.refreshMs, `${key} missing refreshMs`).toBeGreaterThan(0)
    }
  })

  it('includes known layer keys', () => {
    const keys = Object.keys(LAYERS)
    const expected = [
      'flights', 'conflicts', 'events', 'cctv', 'fires',
      'earthquakes', 'weather_alerts', 'nuclear', 'vessels',
      'submarines', 'piracy', 'terrorism', 'cyber',
      'military_bases', 'airspace', 'refugees', 'sanctions',
      'satellites', 'airports', 'notams',
    ]
    for (const k of expected) {
      expect(keys).toContain(k)
    }
  })
})

describe('PRESETS configuration', () => {
  it('has exactly 10 preset entries', () => {
    expect(PRESETS).toHaveLength(10)
  })

  it('every preset has name, lon, lat, alt', () => {
    for (const p of PRESETS) {
      expect(p.name).toBeTruthy()
      expect(typeof p.lon).toBe('number')
      expect(typeof p.lat).toBe('number')
      expect(typeof p.alt).toBe('number')
      expect(p.alt).toBeGreaterThan(0)
    }
  })

  it('includes Global and Gaza presets', () => {
    const names = PRESETS.map(p => p.name)
    expect(names).toContain('Global')
    expect(names).toContain('Gaza')
  })
})

describe('DEFAULT_VISIBLE_LAYERS', () => {
  it('is an array of strings', () => {
    expect(Array.isArray(DEFAULT_VISIBLE_LAYERS)).toBe(true)
    for (const key of DEFAULT_VISIBLE_LAYERS) {
      expect(typeof key).toBe('string')
    }
  })

  it('every default visible layer exists in LAYERS', () => {
    const allKeys = Object.keys(LAYERS)
    for (const key of DEFAULT_VISIBLE_LAYERS) {
      expect(allKeys).toContain(key)
    }
  })

  it('includes flights and conflicts', () => {
    expect(DEFAULT_VISIBLE_LAYERS).toContain('flights')
    expect(DEFAULT_VISIBLE_LAYERS).toContain('conflicts')
  })
})

describe('groupLayers()', () => {
  it('groups layers by their group property', () => {
    const grouped = groupLayers(LAYERS)
    expect(typeof grouped).toBe('object')
    // The LAYERS config has these groups
    expect(Object.keys(grouped)).toContain('Intelligence')
    expect(Object.keys(grouped)).toContain('Environmental')
    expect(Object.keys(grouped)).toContain('Maritime')
    expect(Object.keys(grouped)).toContain('Security')
    expect(Object.keys(grouped)).toContain('Humanitarian')
    expect(Object.keys(grouped)).toContain('Space')
    expect(Object.keys(grouped)).toContain('Infrastructure')
  })

  it('each grouped item has key, label, group, color, refreshMs', () => {
    const grouped = groupLayers(LAYERS)
    for (const [groupName, items] of Object.entries(grouped)) {
      for (const item of items) {
        expect(item.key).toBeTruthy()
        expect(item.label).toBeTruthy()
        expect(item.group).toBe(groupName)
        expect(item.color).toBeTruthy()
        expect(item.refreshMs).toBeGreaterThan(0)
      }
    }
  })

  it('total items across all groups equals 20', () => {
    const grouped = groupLayers(LAYERS)
    let total = 0
    for (const items of Object.values(grouped)) {
      total += items.length
    }
    expect(total).toBe(20)
  })

  it('Intelligence group contains flights, conflicts, events, cctv', () => {
    const grouped = groupLayers(LAYERS)
    const intelKeys = grouped['Intelligence'].map(i => i.key)
    expect(intelKeys).toContain('flights')
    expect(intelKeys).toContain('conflicts')
    expect(intelKeys).toContain('events')
    expect(intelKeys).toContain('cctv')
  })

  it('returns empty object for empty input', () => {
    const grouped = groupLayers({})
    expect(grouped).toEqual({})
  })

  it('handles a single-layer input correctly', () => {
    const grouped = groupLayers({
      test: { label: 'Test', group: 'MyGroup', color: '#000000', refreshMs: 1000 },
    })
    expect(Object.keys(grouped)).toEqual(['MyGroup'])
    expect(grouped['MyGroup']).toHaveLength(1)
    expect(grouped['MyGroup'][0].key).toBe('test')
  })
})
