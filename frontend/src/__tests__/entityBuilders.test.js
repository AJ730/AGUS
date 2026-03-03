import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock Cesium before importing entityBuilders
vi.mock('cesium', () => {
  const mockCartesian3 = { x: 0, y: 0, z: 0 }
  const mockColor = {
    withAlpha: vi.fn(function () { return this }),
    red: 1, green: 0, blue: 0, alpha: 1,
  }
  return {
    Cartesian3: {
      fromDegrees: vi.fn(() => ({ ...mockCartesian3 })),
      fromDegreesArray: vi.fn(() => [{ ...mockCartesian3 }]),
      UNIT_Z: { x: 0, y: 0, z: 1 },
    },
    Cartesian2: vi.fn((x, y) => ({ x, y })),
    Color: {
      fromCssColorString: vi.fn(() => ({ ...mockColor })),
      WHITE: { ...mockColor },
      BLACK: { ...mockColor },
    },
    HeightReference: {
      CLAMP_TO_GROUND: 0,
      NONE: 1,
    },
    NearFarScalar: vi.fn((a, b, c, d) => ({ near: a, nearValue: b, far: c, farValue: d })),
    Math: {
      toRadians: vi.fn((deg) => deg * (3.14159265 / 180)),
    },
    LabelStyle: {
      FILL_AND_OUTLINE: 2,
    },
  }
})

// Mock the airplane module (uses canvas, which is not available in jsdom)
vi.mock('../utils/airplane', () => ({
  getAirplaneBillboard: vi.fn(() => 'mock-airplane-canvas'),
}))

import { buildEntities } from '../utils/entityBuilders'

// Helper: create a mock DataSource with an entities collection
function createMockDataSource() {
  const entities = []
  return {
    entities: {
      removeAll: vi.fn(() => { entities.length = 0 }),
      add: vi.fn((entityDef) => {
        const entity = { ...entityDef }
        entities.push(entity)
        return entity
      }),
      _store: entities,
    },
  }
}

// Helper: create a simple item with lon/lat
function makeItem(lon, lat, extraProps = {}) {
  return {
    properties: { longitude: lon, latitude: lat, ...extraProps },
    geometry: null,
  }
}

describe('buildEntities()', () => {
  let ds

  beforeEach(() => {
    ds = createMockDataSource()
    vi.clearAllMocks()
  })

  it('calls ds.entities.removeAll() before building', () => {
    buildEntities(ds, 'fires', [], { color: '#f97316' })
    expect(ds.entities.removeAll).toHaveBeenCalledTimes(1)
  })

  it('returns 0 for empty items array', () => {
    const count = buildEntities(ds, 'fires', [], { color: '#f97316' })
    expect(count).toBe(0)
  })

  it('skips items with invalid coordinates', () => {
    const items = [
      makeItem(NaN, 10),
      makeItem(20, undefined),
      makeItem(null, null),
    ]
    const count = buildEntities(ds, 'fires', items, { color: '#f97316' })
    expect(count).toBe(0)
  })

  it('processes valid items and returns correct count', () => {
    const items = [
      makeItem(10, 20, { brightness: 350 }),
      makeItem(30, 40, { brightness: 400 }),
      makeItem(50, 60, { brightness: 500 }),
    ]
    const count = buildEntities(ds, 'fires', items, { color: '#f97316' })
    expect(count).toBe(3)
  })

  it('dispatches to the correct builder for flights', () => {
    const items = [
      makeItem(10, 20, {
        callsign: 'TEST123',
        origin_country: 'US',
        baro_altitude: 10000,
        velocity: 250,
        heading: 90,
        is_military: false,
      }),
    ]
    const count = buildEntities(ds, 'flights', items, { color: '#fbbf24' })
    expect(count).toBe(1)

    // The flight builder creates an entity with billboard
    const entity = ds.entities._store[0]
    expect(entity.billboard).toBeDefined()
    expect(entity._tooltipData).toBeDefined()
    expect(entity._tooltipData.rows.Callsign).toBe('TEST123')
    expect(entity._flightData).toBeDefined()
    expect(entity._flightData.callsign).toBe('TEST123')
  })

  it('dispatches to the correct builder for conflicts', () => {
    const items = [
      makeItem(35, 31, {
        event_type: 'Battle',
        fatalities: 5,
        country: 'Syria',
        event_date: '2024-01-01',
      }),
    ]
    const count = buildEntities(ds, 'conflicts', items, { color: '#ef4444' })
    expect(count).toBe(1)
    // Conflicts builder creates 2 entities (outer ring + point)
    expect(ds.entities.add).toHaveBeenCalledTimes(2)
    // The second entity (point) has tooltip data
    const entity = ds.entities._store[1]
    expect(entity._tooltipData.rows.Type).toBe('Battle')
  })

  it('dispatches to the correct builder for earthquakes', () => {
    const items = [
      makeItem(-120, 37, { magnitude: 5.5, depth: 10, place: 'California' }),
    ]
    const count = buildEntities(ds, 'earthquakes', items, { color: '#eab308' })
    expect(count).toBe(1)
    const entity = ds.entities._store[0]
    expect(entity._tooltipData.title).toContain('Earthquake')
    expect(entity._tooltipData.rows.Place).toBe('California')
  })

  it('dispatches to the correct builder for vessels', () => {
    const items = [
      makeItem(2, 51, { name: 'SS Minnow', mmsi: '123456789', speed: 12 }),
    ]
    const count = buildEntities(ds, 'vessels', items, { color: '#3b82f6' })
    expect(count).toBe(1)
    const entity = ds.entities._store[0]
    expect(entity._tooltipData.rows.MMSI).toBe('123456789')
  })

  it('dispatches to the correct builder for satellites', () => {
    const items = [
      makeItem(10, 20, { name: 'ISS (ZARYA)', altitude: 420, norad_id: '25544' }),
    ]
    const count = buildEntities(ds, 'satellites', items, { color: '#e2e8f0' })
    expect(count).toBe(1)
    const entity = ds.entities._store[0]
    expect(entity._tooltipData.title).toContain('ISS')
    // ISS gets a label
    expect(entity.label).toBeDefined()
    expect(entity.label.text).toBe('ISS')
  })

  it('dispatches to the correct builder for cctv', () => {
    const items = [
      makeItem(10, 20, { name: 'Trafalgar Square Cam', stream_url: 'https://example.com/stream' }),
    ]
    const count = buildEntities(ds, 'cctv', items, { color: '#22c55e' })
    expect(count).toBe(1)
    const entity = ds.entities._store[0]
    expect(entity._cctvData).toBeDefined()
    expect(entity._cctvData.stream_url).toBe('https://example.com/stream')
  })

  it('uses default builder for unknown layer keys', () => {
    const items = [
      makeItem(10, 20, {}),
    ]
    const count = buildEntities(ds, 'unknown_layer', items, { color: '#ffffff' })
    expect(count).toBe(1)
    expect(ds.entities.add).toHaveBeenCalled()
  })

  it('reads coordinates from geometry.coordinates when properties lack them', () => {
    const items = [
      {
        properties: { brightness: 300 },
        geometry: { coordinates: [25, 50] },
      },
    ]
    const count = buildEntities(ds, 'fires', items, { color: '#f97316' })
    expect(count).toBe(1)
  })

  it('reads coordinates from lat/lng shorthand properties', () => {
    const items = [
      {
        properties: { lng: 10, lat: 20, brightness: 300 },
        geometry: null,
      },
    ]
    const count = buildEntities(ds, 'fires', items, { color: '#f97316' })
    expect(count).toBe(1)
  })
})

describe('buildEntities() - MAX_VESSELS cap', () => {
  it('caps vessels at 3000 items', () => {
    const ds = createMockDataSource()
    // Create 5000 vessel items
    const items = Array.from({ length: 5000 }, (_, i) =>
      makeItem(i % 360 - 180, i % 180 - 90, { name: `Vessel ${i}`, mmsi: String(i) })
    )
    const count = buildEntities(ds, 'vessels', items, { color: '#3b82f6' })
    expect(count).toBe(3000)
  })

  it('does NOT cap non-vessel layers', () => {
    const ds = createMockDataSource()
    const items = Array.from({ length: 4000 }, (_, i) =>
      makeItem(i % 360 - 180, i % 180 - 90, { brightness: 300 })
    )
    const count = buildEntities(ds, 'fires', items, { color: '#f97316' })
    expect(count).toBe(4000)
  })

  it('handles vessels below the cap without truncation', () => {
    const ds = createMockDataSource()
    const items = Array.from({ length: 100 }, (_, i) =>
      makeItem(i, i, { name: `V${i}` })
    )
    const count = buildEntities(ds, 'vessels', items, { color: '#3b82f6' })
    expect(count).toBe(100)
  })

  it('handles exactly 3000 vessels', () => {
    const ds = createMockDataSource()
    const items = Array.from({ length: 3000 }, (_, i) =>
      makeItem(i % 360 - 180, i % 180 - 90, { name: `V${i}` })
    )
    const count = buildEntities(ds, 'vessels', items, { color: '#3b82f6' })
    expect(count).toBe(3000)
  })
})

describe('buildEntities() - airspace layer (polygon support)', () => {
  it('handles GeoJSON polygon geometry for airspace', () => {
    const ds = createMockDataSource()
    const items = [
      {
        properties: { name: 'Test Airspace', type: 'Restricted' },
        geometry: {
          type: 'Polygon',
          coordinates: [
            [[30, 10], [40, 40], [20, 40], [10, 20], [30, 10]],
          ],
        },
      },
    ]
    const count = buildEntities(ds, 'airspace', items, { color: '#dc2626' })
    // Airspace skips coordinate validation for non-point geometry, so count increments
    expect(count).toBe(1)
    const entity = ds.entities._store[0]
    expect(entity._tooltipData.title).toContain('Airspace')
  })

  it('handles backend coordinate format for airspace', () => {
    const ds = createMockDataSource()
    const items = [
      {
        properties: {
          name: 'Backend Airspace',
          coordinates: [[10, 30], [40, 40], [40, 20]],
        },
        geometry: null,
      },
    ]
    const count = buildEntities(ds, 'airspace', items, { color: '#dc2626' })
    expect(count).toBe(1)
  })
})
