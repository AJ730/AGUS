import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'

// Mock Cesium globally for all component imports
vi.mock('cesium', () => {
  const mockColor = {
    withAlpha: vi.fn(function () { return this }),
  }
  return {
    Color: {
      fromCssColorString: vi.fn(() => ({ ...mockColor })),
    },
  }
})

import BottomBar from '../components/BottomBar'
import AnalyticsCards from '../components/AnalyticsCards'
import Sidebar from '../components/Sidebar'
import TopBar from '../components/TopBar'
import FlightPanel from '../components/FlightPanel'

// ─── BottomBar ────────────────────────────────────────────────────────────────

describe('BottomBar', () => {
  it('renders LIVE status indicator', () => {
    render(<BottomBar cameraAlt={5000} />)
    expect(screen.getByText('LIVE')).toBeInTheDocument()
  })

  it('displays the correct number of OSINT feeds (20)', () => {
    render(<BottomBar cameraAlt={5000} />)
    expect(screen.getByText('Sources: 20 OSINT feeds')).toBeInTheDocument()
  })

  it('shows formatted camera altitude', () => {
    render(<BottomBar cameraAlt={1500} />)
    expect(screen.getByText('Camera: 1.5K km')).toBeInTheDocument()
  })

  it('shows raw altitude when below 1000', () => {
    render(<BottomBar cameraAlt={500} />)
    expect(screen.getByText('Camera: 500 km')).toBeInTheDocument()
  })
})

// ─── AnalyticsCards ───────────────────────────────────────────────────────────

describe('AnalyticsCards', () => {
  const defaultAnalytics = {
    flights: 1234,
    conflicts: 56,
    earthquakes: 7,
    fires: 890,
  }

  it('renders all four metric cards', () => {
    render(<AnalyticsCards analytics={defaultAnalytics} />)
    expect(screen.getByText('Flights')).toBeInTheDocument()
    expect(screen.getByText('Conflicts')).toBeInTheDocument()
    expect(screen.getByText('Earthquakes')).toBeInTheDocument()
    expect(screen.getByText('Fires')).toBeInTheDocument()
  })

  it('formats metric values using fmt()', () => {
    render(<AnalyticsCards analytics={defaultAnalytics} />)
    // 1234 -> "1.2K"
    expect(screen.getByText('1.2K')).toBeInTheDocument()
    // 56 -> "56"
    expect(screen.getByText('56')).toBeInTheDocument()
    // 7 -> "7"
    expect(screen.getByText('7')).toBeInTheDocument()
    // 890 -> "890"
    expect(screen.getByText('890')).toBeInTheDocument()
  })

  it('renders 0 for missing analytics values', () => {
    render(<AnalyticsCards analytics={{}} />)
    const zeros = screen.getAllByText('0')
    expect(zeros).toHaveLength(4)
  })

  it('applies the correct color to each metric value', () => {
    render(<AnalyticsCards analytics={defaultAnalytics} />)
    // The flights value should be colored #fbbf24
    const flightsValue = screen.getByText('1.2K')
    expect(flightsValue).toHaveStyle({ color: '#fbbf24' })
  })
})

// ─── Sidebar ──────────────────────────────────────────────────────────────────

describe('Sidebar', () => {
  const testLayers = {
    flights:   { label: 'Flights',    group: 'Intelligence', color: '#fbbf24', refreshMs: 30000 },
    conflicts: { label: 'Conflicts',  group: 'Intelligence', color: '#ef4444', refreshMs: 300000 },
    fires:     { label: 'Fire Spots', group: 'Environmental', color: '#f97316', refreshMs: 300000 },
  }

  const testLayerState = {
    flights:   { visible: true,  count: 1500 },
    conflicts: { visible: false, count: 42 },
    fires:     { visible: true,  count: 300 },
  }

  const defaultProps = {
    layers: testLayers,
    layerState: testLayerState,
    onToggle: vi.fn(),
    collapsedGroups: {},
    onToggleGroup: vi.fn(),
    isOpen: true,
  }

  it('renders layer groups', () => {
    render(<Sidebar {...defaultProps} />)
    expect(screen.getByText('INTELLIGENCE')).toBeInTheDocument()
    expect(screen.getByText('ENVIRONMENTAL')).toBeInTheDocument()
  })

  it('renders layer labels within groups', () => {
    render(<Sidebar {...defaultProps} />)
    expect(screen.getByText('Flights')).toBeInTheDocument()
    expect(screen.getByText('Conflicts')).toBeInTheDocument()
    expect(screen.getByText('Fire Spots')).toBeInTheDocument()
  })

  it('shows formatted counts for each layer', () => {
    render(<Sidebar {...defaultProps} />)
    // 1500 -> "1.5K"
    expect(screen.getByText('1.5K')).toBeInTheDocument()
    // 42 -> "42"
    expect(screen.getByText('42')).toBeInTheDocument()
    // 300 -> "300"
    expect(screen.getByText('300')).toBeInTheDocument()
  })

  it('marks active layers with the active class', () => {
    render(<Sidebar {...defaultProps} />)
    const flightsCard = screen.getByText('Flights').closest('.layer-card')
    expect(flightsCard).toHaveClass('active')

    const conflictsCard = screen.getByText('Conflicts').closest('.layer-card')
    expect(conflictsCard).not.toHaveClass('active')
  })

  it('calls onToggle when a layer is clicked', () => {
    const onToggle = vi.fn()
    render(<Sidebar {...defaultProps} onToggle={onToggle} />)
    fireEvent.click(screen.getByText('Flights'))
    expect(onToggle).toHaveBeenCalledWith('flights')
  })

  it('calls onToggleGroup when a group header is clicked', () => {
    const onToggleGroup = vi.fn()
    render(<Sidebar {...defaultProps} onToggleGroup={onToggleGroup} />)
    fireEvent.click(screen.getByText('INTELLIGENCE'))
    expect(onToggleGroup).toHaveBeenCalledWith('Intelligence')
  })

  it('hides layers when group is collapsed', () => {
    render(<Sidebar {...defaultProps} collapsedGroups={{ Intelligence: true }} />)
    // Group header should still be visible
    expect(screen.getByText('INTELLIGENCE')).toBeInTheDocument()
    // Layers in the collapsed group should not render
    expect(screen.queryByText('Flights')).not.toBeInTheDocument()
    expect(screen.queryByText('Conflicts')).not.toBeInTheDocument()
    // Layers in non-collapsed groups should still render
    expect(screen.getByText('Fire Spots')).toBeInTheDocument()
  })

  it('adds open class when sidebar is open', () => {
    const { container } = render(<Sidebar {...defaultProps} isOpen={true} />)
    const aside = container.querySelector('aside.sidebar')
    expect(aside).toHaveClass('open')
  })

  it('does not add open class when sidebar is closed', () => {
    const { container } = render(<Sidebar {...defaultProps} isOpen={false} />)
    const aside = container.querySelector('aside.sidebar')
    expect(aside).not.toHaveClass('open')
  })

  it('renders checkbox inputs reflecting visible state', () => {
    render(<Sidebar {...defaultProps} />)
    const checkboxes = screen.getAllByRole('checkbox')
    // Three layers -> three checkboxes
    expect(checkboxes).toHaveLength(3)
    // flights=visible, conflicts=not, fires=visible
    expect(checkboxes[0]).toBeChecked()     // flights
    expect(checkboxes[1]).not.toBeChecked() // conflicts
    expect(checkboxes[2]).toBeChecked()     // fires
  })
})

// ─── TopBar ───────────────────────────────────────────────────────────────────

describe('TopBar', () => {
  const defaultProps = {
    onMenuToggle: vi.fn(),
    onFlyToPreset: vi.fn(),
    searchQuery: '',
    onSearchChange: vi.fn(),
    onSearch: vi.fn(),
    cameraAlt: 15000,
  }

  it('renders the AGUS brand title', () => {
    render(<TopBar {...defaultProps} />)
    expect(screen.getByText('AGUS')).toBeInTheDocument()
    expect(screen.getByText('OSINT Intelligence Platform')).toBeInTheDocument()
  })

  it('renders all 10 preset buttons', () => {
    render(<TopBar {...defaultProps} />)
    expect(screen.getByText('Global')).toBeInTheDocument()
    expect(screen.getByText('Middle East')).toBeInTheDocument()
    expect(screen.getByText('Ukraine')).toBeInTheDocument()
    expect(screen.getByText('Gaza')).toBeInTheDocument()
  })

  it('calls onFlyToPreset when a preset button is clicked', () => {
    const onFlyToPreset = vi.fn()
    render(<TopBar {...defaultProps} onFlyToPreset={onFlyToPreset} />)
    fireEvent.click(screen.getByText('Gaza'))
    expect(onFlyToPreset).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Gaza', lon: 34.47, lat: 31.5 })
    )
  })

  it('calls onMenuToggle when menu button is clicked', () => {
    const onMenuToggle = vi.fn()
    render(<TopBar {...defaultProps} onMenuToggle={onMenuToggle} />)
    // The menu button has ☰ text (&#9776;)
    const menuBtn = screen.getByRole('button', { name: /☰/ })
    fireEvent.click(menuBtn)
    expect(onMenuToggle).toHaveBeenCalled()
  })

  it('displays formatted camera altitude', () => {
    render(<TopBar {...defaultProps} cameraAlt={15000} />)
    expect(screen.getByText('15.0K km')).toBeInTheDocument()
  })

  it('shows the search input with placeholder', () => {
    render(<TopBar {...defaultProps} />)
    const input = screen.getByPlaceholderText('Search location...')
    expect(input).toBeInTheDocument()
  })

  it('calls onSearchChange when input value changes', () => {
    const onSearchChange = vi.fn()
    render(<TopBar {...defaultProps} onSearchChange={onSearchChange} />)
    const input = screen.getByPlaceholderText('Search location...')
    fireEvent.change(input, { target: { value: 'London' } })
    expect(onSearchChange).toHaveBeenCalledWith('London')
  })

  it('calls onSearch when Enter key is pressed', () => {
    const onSearch = vi.fn()
    render(<TopBar {...defaultProps} onSearch={onSearch} />)
    const input = screen.getByPlaceholderText('Search location...')
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onSearch).toHaveBeenCalled()
  })
})

// ─── FlightPanel ──────────────────────────────────────────────────────────────

describe('FlightPanel', () => {
  const flightData = {
    callsign: 'UAL1234',
    country: 'United States',
    icao24: 'abc123',
    altitude: 10000,
    speed: 250,
    heading: 180,
    vertical_rate: 2.5,
    squawk: '1200',
    squawk_alert: null,
    on_ground: false,
    is_military: false,
  }

  it('renders null when no flight is provided', () => {
    const { container } = render(<FlightPanel flight={null} onClose={vi.fn()} onTrack={vi.fn()} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders flight callsign in the header', () => {
    render(<FlightPanel flight={flightData} onClose={vi.fn()} onTrack={vi.fn()} />)
    expect(screen.getByText('UAL1234')).toBeInTheDocument()
  })

  it('displays CIVILIAN badge for non-military flights', () => {
    render(<FlightPanel flight={flightData} onClose={vi.fn()} onTrack={vi.fn()} />)
    expect(screen.getByText('CIVILIAN')).toBeInTheDocument()
  })

  it('displays MILITARY badge for military flights', () => {
    render(<FlightPanel flight={{ ...flightData, is_military: true }} onClose={vi.fn()} onTrack={vi.fn()} />)
    expect(screen.getByText('MILITARY')).toBeInTheDocument()
  })

  it('shows flight details: country, icao24, altitude, speed, heading', () => {
    render(<FlightPanel flight={flightData} onClose={vi.fn()} onTrack={vi.fn()} />)
    expect(screen.getByText('United States')).toBeInTheDocument()
    expect(screen.getByText('abc123')).toBeInTheDocument()
    expect(screen.getByText('250 m/s')).toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn()
    render(<FlightPanel flight={flightData} onClose={onClose} onTrack={vi.fn()} />)
    // The close button has × character
    const closeBtn = screen.getByRole('button', { name: /×/ })
    fireEvent.click(closeBtn)
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onTrack with icao24 when TRACK FLIGHT is clicked', () => {
    const onTrack = vi.fn()
    render(<FlightPanel flight={flightData} onClose={vi.fn()} onTrack={onTrack} />)
    fireEvent.click(screen.getByText('TRACK FLIGHT'))
    expect(onTrack).toHaveBeenCalledWith('abc123')
  })

  it('shows squawk alert info when present', () => {
    const alertFlight = { ...flightData, squawk: '7700', squawk_alert: 'EMERGENCY' }
    render(<FlightPanel flight={alertFlight} onClose={vi.fn()} onTrack={vi.fn()} />)
    expect(screen.getByText(/7700/)).toBeInTheDocument()
    expect(screen.getByText(/EMERGENCY/)).toBeInTheDocument()
  })

  it('shows on-ground status', () => {
    render(<FlightPanel flight={{ ...flightData, on_ground: true }} onClose={vi.fn()} onTrack={vi.fn()} />)
    expect(screen.getByText('Yes')).toBeInTheDocument()
  })
})
