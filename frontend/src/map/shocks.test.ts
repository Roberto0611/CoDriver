import { describe, expect, it } from 'vitest'
import type { Map as MLMap } from 'maplibre-gl'

import { resaltarShock } from './shocks'
import { CLOSURE_RED, MAP_BG, MAP_BG_DIM, ROAD } from './style'

/** Mapa falso: solo los métodos que usa shocks.ts. */
function mapaFalso() {
  const paint = new Map<string, Record<string, unknown>>([
    ['background', { 'background-color': MAP_BG }],
    ['roads-local-Centro', { 'line-color': ROAD.local }],
    ['roads-primary-casing-Centro', { 'line-color': ROAD.primaryCasing }],
    ['roads-primary-Centro', { 'line-color': ROAD.primary }],
    ['trail-nuez-line', { 'line-color': '#4F46E5' }],
  ])
  const handlers = new Map<string, Set<() => void>>()
  let removed = false

  const fake = {
    getLayersOrder: () => (removed ? [] : [...paint.keys()]),
    getLayer: (id: string) => (removed || !paint.has(id) ? undefined : { id }),
    getPaintProperty: (id: string, prop: string) => paint.get(id)?.[prop],
    setPaintProperty: (id: string, prop: string, value: unknown) => {
      if (removed || !paint.has(id)) throw new Error(`capa inexistente: ${id}`)
      paint.get(id)![prop] = value
    },
    on: (type: string, fn: () => void) => {
      if (!handlers.has(type)) handlers.set(type, new Set())
      handlers.get(type)!.add(fn)
    },
    off: (type: string, fn: () => void) => handlers.get(type)?.delete(fn),
    flyTo: () => {},
  }

  return {
    map: fake as unknown as MLMap,
    color: (id: string) => paint.get(id)?.['line-color'],
    fondo: () => paint.get('background')?.['background-color'],
    agregarCapa: (id: string, color: string) => {
      paint.set(id, { 'line-color': color })
      for (const fn of handlers.get('styledata') ?? []) fn()
    },
    listeners: () => handlers.get('styledata')?.size ?? 0,
    remove: () => {
      removed = true
    },
  }
}

const cierre = (road: string) => ({
  type: 'closure' as const,
  zoneCenter: [-100.309, 25.6714] as [number, number],
  road,
})
const lluvia = { type: 'rain' as const }

/** Nombres de calle resaltados en la expresión actual de una capa ([] si es color plano). */
const callesResaltadas = (color: unknown): string[] =>
  JSON.stringify(color ?? '')
    .match(/"in","([^"]+)"/g)
    ?.map((m) => m.slice(6, -1)) ?? []

describe('resaltarShock: cierres', () => {
  it('pinta la calle cerrada y deja el casing sin tocar', () => {
    const f = mapaFalso()
    resaltarShock(f.map, cierre('Constitución'))
    expect(callesResaltadas(f.color('roads-local-Centro'))).toEqual(['Constitución'])
    expect(JSON.stringify(f.color('roads-primary-Centro'))).toContain(CLOSURE_RED)
    expect(f.color('roads-primary-casing-Centro')).toBe(ROAD.primaryCasing)
    expect(f.color('trail-nuez-line')).toBe('#4F46E5')
  })

  it('dos cierres limpiados en orden de llegada restauran el color base', () => {
    const f = mapaFalso()
    const limpiarA = resaltarShock(f.map, cierre('Constitución'))
    const limpiarB = resaltarShock(f.map, cierre('Gonzalitos'))
    expect(callesResaltadas(f.color('roads-local-Centro')).sort()).toEqual([
      'Constitución',
      'Gonzalitos',
    ])

    limpiarA()
    expect(callesResaltadas(f.color('roads-local-Centro'))).toEqual(['Gonzalitos'])

    limpiarB()
    expect(f.color('roads-local-Centro')).toBe(ROAD.local)
    expect(f.color('roads-primary-Centro')).toBe(ROAD.primary)
    expect(f.listeners()).toBe(0)
  })

  it('dos cierres limpiados en orden inverso restauran el color base', () => {
    const f = mapaFalso()
    const limpiarA = resaltarShock(f.map, cierre('Constitución'))
    const limpiarB = resaltarShock(f.map, cierre('Gonzalitos'))

    limpiarB()
    expect(callesResaltadas(f.color('roads-local-Centro'))).toEqual(['Constitución'])

    limpiarA()
    expect(f.color('roads-local-Centro')).toBe(ROAD.local)
    expect(f.color('roads-primary-Centro')).toBe(ROAD.primary)
    expect(f.listeners()).toBe(0)
  })

  it('el mismo camino cerrado dos veces sigue rojo hasta la última limpieza', () => {
    const f = mapaFalso()
    const limpiarA = resaltarShock(f.map, cierre('Constitución'))
    const limpiarB = resaltarShock(f.map, cierre('Constitución'))
    limpiarA()
    expect(callesResaltadas(f.color('roads-local-Centro'))).toEqual(['Constitución'])
    limpiarB()
    expect(f.color('roads-local-Centro')).toBe(ROAD.local)
  })

  it('las capas que cargan tarde reciben los cierres activos y el listener se va al final', () => {
    const f = mapaFalso()
    const limpiarA = resaltarShock(f.map, cierre('Constitución'))
    const limpiarB = resaltarShock(f.map, cierre('Gonzalitos'))
    expect(f.listeners()).toBe(1)

    limpiarA()
    f.agregarCapa('roads-secondary-Tec', ROAD.secondary)
    expect(callesResaltadas(f.color('roads-secondary-Tec'))).toEqual(['Gonzalitos'])

    limpiarB()
    expect(f.color('roads-secondary-Tec')).toBe(ROAD.secondary)
    expect(f.listeners()).toBe(0)

    // Sin cierres activos, una capa nueva queda con su color.
    f.agregarCapa('roads-tertiary-Tec', ROAD.tertiary)
    expect(f.color('roads-tertiary-Tec')).toBe(ROAD.tertiary)
  })

  it('llamar la limpieza dos veces no quita un cierre ajeno', () => {
    const f = mapaFalso()
    const limpiarA = resaltarShock(f.map, cierre('Constitución'))
    resaltarShock(f.map, cierre('Gonzalitos'))
    limpiarA()
    limpiarA()
    expect(callesResaltadas(f.color('roads-local-Centro'))).toEqual(['Gonzalitos'])
  })

  it('limpiar después de quitar el mapa no lanza', () => {
    const f = mapaFalso()
    const limpiarA = resaltarShock(f.map, cierre('Constitución'))
    const limpiarB = resaltarShock(f.map, cierre('Gonzalitos'))
    f.remove()
    expect(() => {
      limpiarA()
      limpiarB()
      limpiarB()
    }).not.toThrow()
    expect(f.listeners()).toBe(0)
  })
})

describe('resaltarShock: lluvia', () => {
  it('dos lluvias y ambas limpiezas restauran el fondo', () => {
    const f = mapaFalso()
    const limpiarA = resaltarShock(f.map, lluvia)
    const limpiarB = resaltarShock(f.map, lluvia)
    expect(f.fondo()).toBe(MAP_BG_DIM)

    limpiarA()
    expect(f.fondo()).toBe(MAP_BG_DIM)

    limpiarB()
    expect(f.fondo()).toBe(MAP_BG)
  })

  it('la limpieza doble no restaura mientras otra lluvia sigue activa', () => {
    const f = mapaFalso()
    const limpiarA = resaltarShock(f.map, lluvia)
    const limpiarB = resaltarShock(f.map, lluvia)
    limpiarB()
    limpiarB()
    expect(f.fondo()).toBe(MAP_BG_DIM)
    limpiarA()
    expect(f.fondo()).toBe(MAP_BG)
  })

  it('limpiar después de quitar el mapa no lanza', () => {
    const f = mapaFalso()
    const limpiar = resaltarShock(f.map, lluvia)
    f.remove()
    expect(() => {
      limpiar()
      limpiar()
    }).not.toThrow()
  })
})

describe('resaltarShock: surge y mapa nulo', () => {
  it('surge no repinta y su limpieza no hace nada', () => {
    const f = mapaFalso()
    const limpiar = resaltarShock(f.map, { type: 'surge', zoneCenter: [-100.2895, 25.6515] })
    expect(f.color('roads-local-Centro')).toBe(ROAD.local)
    expect(f.fondo()).toBe(MAP_BG)
    expect(() => limpiar()).not.toThrow()
  })

  it('sin mapa devuelve una limpieza vacía', () => {
    const limpiar = resaltarShock(null, cierre('Constitución'))
    expect(() => limpiar()).not.toThrow()
  })
})
