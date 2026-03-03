import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the Cesium module before importing helpers
vi.mock('cesium', () => {
  const mockColor = {
    withAlpha: vi.fn(function (a) {
      return { ...this, alpha: a }
    }),
    red: 1,
    green: 0,
    blue: 0,
  }
  return {
    Color: {
      fromCssColorString: vi.fn(() => ({ ...mockColor })),
    },
  }
})

import { fmt, clamp, hexColor } from '../utils/helpers'
import * as Cesium from 'cesium'

describe('fmt() - number formatting', () => {
  it('formats numbers below 1000 as plain strings', () => {
    expect(fmt(0)).toBe('0')
    expect(fmt(1)).toBe('1')
    expect(fmt(42)).toBe('42')
    expect(fmt(999)).toBe('999')
  })

  it('formats thousands with K suffix', () => {
    expect(fmt(1000)).toBe('1.0K')
    expect(fmt(1500)).toBe('1.5K')
    expect(fmt(25000)).toBe('25.0K')
    expect(fmt(999999)).toBe('1000.0K')
  })

  it('formats millions with M suffix', () => {
    expect(fmt(1000000)).toBe('1.0M')
    expect(fmt(1500000)).toBe('1.5M')
    expect(fmt(10000000)).toBe('10.0M')
  })

  it('handles edge case at 1000 boundary', () => {
    expect(fmt(999)).toBe('999')
    expect(fmt(1000)).toBe('1.0K')
  })

  it('handles edge case at 1000000 boundary', () => {
    expect(fmt(999999)).toBe('1000.0K')
    expect(fmt(1000000)).toBe('1.0M')
  })
})

describe('clamp() - value clamping', () => {
  it('returns value when within range', () => {
    expect(clamp(5, 0, 10)).toBe(5)
    expect(clamp(0, 0, 10)).toBe(0)
    expect(clamp(10, 0, 10)).toBe(10)
  })

  it('clamps to min when value is below', () => {
    expect(clamp(-5, 0, 10)).toBe(0)
    expect(clamp(-100, -50, 50)).toBe(-50)
  })

  it('clamps to max when value is above', () => {
    expect(clamp(15, 0, 10)).toBe(10)
    expect(clamp(100, -50, 50)).toBe(50)
  })

  it('works with floating point values', () => {
    expect(clamp(0.5, 0, 1)).toBe(0.5)
    expect(clamp(-0.1, 0, 1)).toBe(0)
    expect(clamp(1.1, 0, 1)).toBe(1)
  })

  it('works when min equals max', () => {
    expect(clamp(5, 3, 3)).toBe(3)
    expect(clamp(1, 3, 3)).toBe(3)
  })
})

describe('hexColor() - Cesium color from hex', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls Cesium.Color.fromCssColorString with the hex value', () => {
    hexColor('#ff0000')
    expect(Cesium.Color.fromCssColorString).toHaveBeenCalledWith('#ff0000')
  })

  it('calls withAlpha with default alpha of 1', () => {
    const result = hexColor('#00ff00')
    expect(result.alpha).toBe(1)
  })

  it('calls withAlpha with provided alpha', () => {
    const result = hexColor('#0000ff', 0.5)
    expect(result.alpha).toBe(0.5)
  })

  it('passes different hex strings correctly', () => {
    hexColor('#abcdef', 0.3)
    expect(Cesium.Color.fromCssColorString).toHaveBeenCalledWith('#abcdef')
  })
})
