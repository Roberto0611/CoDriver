import { describe, expect, it } from 'vitest'
import {
  distSq,
  formatNumber,
  isJsonResponse,
  nearestZones,
  zonaCentrosFromGeoJSON,
  ZONAS_LIST,
  type ZonaCentro,
} from './zones'

const zonas: ZonaCentro[] = [
  { zona: 'Centro', centro: [-100.309, 25.671] },
  { zona: 'Tec', centro: [-100.2895, 25.6515] },
  { zona: 'Valle', centro: [-100.359, 25.651] },
  { zona: 'Apodaca', centro: [-100.19, 25.78] },
]

describe('nearestZones', () => {
  it('orders by distance to the center', () => {
    const near = nearestZones(zonas, [-100.29, 25.65], new Set(), 4)
    expect(near).toEqual(['Tec', 'Centro', 'Valle', 'Apodaca'])
  })

  it('skips zones already loaded and respects the count', () => {
    const near = nearestZones(zonas, [-100.29, 25.65], new Set(['Tec']), 2)
    expect(near).toEqual(['Centro', 'Valle'])
  })

  it('returns nothing for a non-positive count', () => {
    expect(nearestZones(zonas, [0, 0], new Set(), 0)).toEqual([])
    expect(nearestZones(zonas, [0, 0], new Set(), -3)).toEqual([])
  })
})

describe('distSq', () => {
  it('is zero for the same point and symmetric', () => {
    expect(distSq([1, 2], [1, 2])).toBe(0)
    expect(distSq([1, 2], [4, 6])).toBe(distSq([4, 6], [1, 2]))
    expect(distSq([1, 2], [4, 6])).toBe(25)
  })
})

describe('zonaCentrosFromGeoJSON', () => {
  it('reads zona and centro from feature properties', () => {
    const geo = {
      features: [{ properties: { zona: 'Tec', centro: [-100.29, 25.65] as [number, number] } }],
    }
    expect(zonaCentrosFromGeoJSON(geo)).toEqual([{ zona: 'Tec', centro: [-100.29, 25.65] }])
  })
})

describe('isJsonResponse', () => {
  const res = (ok: boolean, ct: string | null) => ({ ok, headers: { get: () => ct } })

  it('accepts a JSON body', () => {
    expect(isJsonResponse(res(true, 'application/json; charset=utf-8'))).toBe(true)
  })

  it('rejects the Vite HTML fallback and failed responses', () => {
    expect(isJsonResponse(res(true, 'text/html'))).toBe(false)
    expect(isJsonResponse(res(false, 'application/json'))).toBe(false)
    expect(isJsonResponse(res(true, null))).toBe(false)
  })
})

describe('ZONAS_LIST', () => {
  it('has the 14 zones of the simulator, without duplicates', () => {
    expect(ZONAS_LIST).toHaveLength(14)
    expect(new Set(ZONAS_LIST).size).toBe(14)
    expect(ZONAS_LIST).toContain('Tec')
  })
})

describe('formatNumber', () => {
  it('uses thousands separators', () => {
    expect(formatNumber(1234567)).toMatch(/1.234.567/)
  })
})
