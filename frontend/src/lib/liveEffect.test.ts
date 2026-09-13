import { describe, it, expect } from 'vitest'

import type { Decision } from '../contract'
import type { LiveOffer, LiveSnapshot } from './live'
import type { LiveShockSeen, LiveState } from './liveAccum'
import { efectoShock, zonasDePuntos } from './liveEffect'
import type { Frame, Tramo, TurnoData } from './turno'

// Puntos 0-1 en Centro, 2-3 en Tec. Desordenados a propósito: manda `properties.i`.
const PUNTOS: GeoJSON.FeatureCollection = {
  type: 'FeatureCollection',
  features: [
    [2, 'Tec'],
    [0, 'Centro'],
    [3, 'Tec'],
    [1, 'Centro'],
  ].map(([i, zona]) => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [0, 0] },
    properties: { i, zona },
  })),
}

const tramo = (t_salida: number, t_llegada: number, desde: number, hasta: number): Tramo => ({
  t_salida,
  t_llegada,
  desde,
  hasta,
  clave: `${desde}-${hasta}`,
})

const turno = (tramos: Tramo[], frames: Frame[] = []): TurnoData =>
  ({ tramos, frames }) as unknown as TurnoData

const decision = (oferta_id: string, accion: Decision['accion']): Decision => ({
  t: 0,
  oferta_id,
  accion,
  terminos: {},
  razon: '',
  restriccion: null,
})

const frame = (t: number, decisiones: Decision[]): Frame => ({
  t,
  ofertas: [],
  decisiones,
  llegada: null,
  cobro: 0,
  ganado: 0,
})

const oferta = (order_id: string, minute: number, pickup_zone: string): LiveOffer => ({
  order_id,
  minute,
  pickup: 0,
  dropoff: 2,
  pickup_zone,
  dropoff_zone: 'Tec',
  pay_mxn: 50,
})

function estado(partes: Partial<LiveState>, cancelados = { greedy: 0, nuez: 0 }): LiveState {
  return {
    snapshot: {
      greedy: { cancelled: cancelados.greedy },
      nuez: { cancelled: cancelados.nuez },
    } as unknown as LiveSnapshot,
    greedy: turno([]),
    nuez: turno([]),
    shocks: [],
    offers: [],
    ...partes,
  }
}

const CIERRE: LiveShockSeen = {
  type: 'closure',
  zone: 0,
  zone_name: 'Centro',
  road: 'Constitución',
  starts_at_min: 30,
  ends_at_min: 70,
  multiplier: 1,
  cancelled_at_start: { greedy: 0, nuez: 1 },
}

const SURGE: LiveShockSeen = {
  type: 'surge',
  zone: 4,
  zone_name: 'Tec',
  road: null,
  starts_at_min: 40,
  ends_at_min: 70,
  multiplier: 1.8,
  cancelled_at_start: { greedy: 0, nuez: 0 },
}

describe('zonasDePuntos', () => {
  it('indexa la zona por properties.i', () => {
    expect(zonasDePuntos(PUNTOS)).toEqual(['Centro', 'Centro', 'Tec', 'Tec'])
  })
})

describe('efectoShock: cierre', () => {
  const zonas = zonasDePuntos(PUNTOS)

  it('cuenta los tramos que salen durante el cierre y tocan la zona, con sus minutos', () => {
    const s = estado({
      nuez: turno([
        tramo(20, 35, 0, 2), // salió antes del cierre
        tramo(31, 43.5, 2, 1), // llega a Centro
        tramo(45, 50, 0, 3), // sale de Centro
        tramo(50, 60, 2, 3), // Tec a Tec: no toca la zona
        tramo(70, 80, 0, 2), // el cierre ya acabó
      ]),
      greedy: turno([tramo(30, 48, 1, 1)]),
    })
    const e = efectoShock(s, CIERRE, zonas)
    expect(e.nuez.route).toEqual({ kind: 'closure', zone: 'Centro', legs: 2, minutes: 17.5 })
    expect(e.greedy.route).toEqual({ kind: 'closure', zone: 'Centro', legs: 1, minutes: 18 })
  })

  it('sin puntos cargados no inventa un cero', () => {
    const e = efectoShock(estado({ nuez: turno([tramo(31, 40, 0, 2)]) }), CIERRE, [])
    expect(e.nuez.route).toBeNull()
  })

  it('los cancelados son los de ahora menos los del momento del shock', () => {
    const e = efectoShock(estado({}, { greedy: 2, nuez: 4 }), CIERRE, zonas)
    expect(e.greedy.cancelled).toBe(2)
    expect(e.nuez.cancelled).toBe(3)
  })
})

describe('efectoShock: surge', () => {
  it('cuenta las ofertas que nacen en la zona durante el surge y cuántas tomó cada uno', () => {
    const s = estado({
      offers: [
        oferta('o_1', 39, 'Tec'), // antes del surge
        oferta('o_2', 40, 'Tec'),
        oferta('o_3', 41, 'Centro'), // otra zona
        oferta('o_4', 55, 'Tec'),
        oferta('o_5', 70, 'Tec'), // ya acabó
      ],
      greedy: turno(
        [],
        [
          frame(39, [decision('o_1', 'aceptar')]),
          frame(40, [decision('o_2', 'aceptar')]),
          frame(55, [decision('o_4', 'aceptar')]),
        ]
      ),
      nuez: turno(
        [],
        [frame(40, [decision('o_2', 'saltar')]), frame(55, [decision('o_4', 'aceptar')])]
      ),
    })
    const e = efectoShock(s, SURGE, [])
    expect(e.greedy.route).toEqual({ kind: 'surge', zone: 'Tec', offers: 2, accepted: 2 })
    expect(e.nuez.route).toEqual({ kind: 'surge', zone: 'Tec', offers: 2, accepted: 1 })
  })

  it('la lluvia no tiene zona que medir', () => {
    const lluvia: LiveShockSeen = { ...SURGE, type: 'rain', zone: null, zone_name: null }
    expect(efectoShock(estado({}), lluvia, []).nuez.route).toBeNull()
  })
})
