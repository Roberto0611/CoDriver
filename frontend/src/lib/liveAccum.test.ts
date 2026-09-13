import { describe, it, expect } from 'vitest'

import type { Decision } from '../contract'
import type { LiveAgent, LiveShock, LiveSnapshot } from './live'
import { applySnapshot, countersOf, firstDecisionFrom, initLiveState } from './liveAccum'
import type { Frame, Tramo } from './turno'

// ── Fábricas ─────────────────────────────────────────────────────────────

function decision(t: number, accion: Decision['accion'] = 'saltar'): Decision {
  return {
    t,
    oferta_id: `o_${t}`,
    accion,
    terminos: { pago_neto: 40, minutos: 20 },
    razon: `razon ${t}`,
    restriccion: null,
  }
}

function frame(t: number, overrides: Partial<Frame> = {}): Frame {
  return { t, ofertas: [], decisiones: [], llegada: null, cobro: 0, ganado: 0, ...overrides }
}

function tramo(t: number): Tramo {
  return { t_salida: t, t_llegada: t + 5, desde: t, hasta: t + 1, clave: `${t}-${t + 1}` }
}

function agent(overrides: Partial<LiveAgent> = {}): LiveAgent {
  return {
    position: 4,
    coords: [-100.29, 25.65],
    earnings_mxn: 0,
    deliveries: 0,
    skipped: 0,
    cancelled: 0,
    route: [],
    last_decision: null,
    frames: [],
    new_legs: [],
    geometry: {},
    result: null,
    ...overrides,
  }
}

const CIERRE: LiveShock = {
  type: 'closure',
  zone: 0,
  zone_name: 'Centro',
  road: 'Constitución',
  starts_at_min: 30,
  ends_at_min: 70,
  multiplier: 1,
}

function snap(
  minute: number,
  overrides: Partial<Omit<LiveSnapshot, 'greedy' | 'nuez'>> & {
    greedy?: Partial<LiveAgent>
    nuez?: Partial<LiveAgent>
  } = {}
): LiveSnapshot {
  const { greedy, nuez, ...rest } = overrides
  return {
    session_id: 'live-2005-ab12',
    minute,
    duration_min: 120,
    start_hour: 14,
    seed: 2005,
    status: 'running',
    active_shocks: [],
    offers_this_tick: [],
    greedy: agent(greedy),
    nuez: agent(nuez),
    ...rest,
  }
}

// ── Tests ────────────────────────────────────────────────────────────────

describe('initLiveState', () => {
  it('arranca sin frames y en $0 los dos', () => {
    const s = initLiveState(snap(0))
    expect(s.greedy.frames.length).toBe(0)
    expect(s.nuez.frames.length).toBe(0)
    expect(s.greedy.meta.ganado).toBe(0)
    expect(s.nuez.meta.ganado).toBe(0)
  })

  it('arma el config del snapshot, con el ancla en la posición inicial', () => {
    const s = initLiveState(snap(0), { vehiculo: 'bike', margen_min: 5 })
    expect(s.nuez.config).toMatchObject({
      duracion_min: 120,
      hora_inicio: 14,
      seed: 2005,
      vehiculo: 'bike',
      margen_min: 5,
      ancla: { lat: 25.65, lon: -100.29 },
    })
  })
})

describe('applySnapshot', () => {
  it('pega frames y tramos en orden', () => {
    let s = initLiveState(snap(0))
    s = applySnapshot(s, snap(1, { nuez: { frames: [frame(0)], new_legs: [tramo(0)] } }))
    s = applySnapshot(s, snap(2, { nuez: { frames: [frame(1)], new_legs: [tramo(1)] } }))
    expect(s.nuez.frames.map((f) => f.t)).toEqual([0, 1])
    expect(s.nuez.tramos.map((x) => x.clave)).toEqual(['0-1', '1-2'])
    expect(s.snapshot.minute).toBe(2)
  })

  it('no pierde geometría de un tick anterior', () => {
    let s = initLiveState(snap(0))
    const linea: [number, number][] = [
      [-100.29, 25.65],
      [-100.3, 25.66],
    ]
    s = applySnapshot(s, snap(1, { greedy: { geometry: { '0-1': linea } } }))
    s = applySnapshot(s, snap(2, { greedy: { geometry: {} } }))
    expect(s.greedy.geometria['0-1']).toEqual(linea)
  })

  it('la geometría es de cada agente, no compartida', () => {
    let s = initLiveState(snap(0))
    s = applySnapshot(s, snap(1, { greedy: { geometry: { '0-1': [[0, 0]] } } }))
    expect(s.nuez.geometria['0-1']).toBeUndefined()
  })

  it('guarda el shock aunque ya haya expirado', () => {
    let s = initLiveState(snap(0))
    s = applySnapshot(s, snap(30, { active_shocks: [CIERRE] }))
    s = applySnapshot(s, snap(31, { active_shocks: [CIERRE] }))
    s = applySnapshot(s, snap(71, { active_shocks: [] }))
    expect(s.shocks).toHaveLength(1)
    expect(s.shocks[0]).toMatchObject(CIERRE)
  })

  it('anota los cancelados de cada agente cuando ve el shock por primera vez', () => {
    let s = initLiveState(snap(0))
    s = applySnapshot(s, snap(30, { active_shocks: [CIERRE], nuez: { cancelled: 2 } }))
    s = applySnapshot(s, snap(40, { active_shocks: [CIERRE], nuez: { cancelled: 5 } }))
    expect(s.shocks[0].cancelled_at_start).toEqual({ greedy: 0, nuez: 2 })
  })

  it('llena meta con los totales en vivo y con `result` al terminar', () => {
    let s = initLiveState(snap(0))
    s = applySnapshot(
      s,
      snap(10, {
        offers_this_tick: [
          {
            order_id: 'o_1',
            minute: 9,
            pickup: 1,
            dropoff: 2,
            pickup_zone: 'Tec',
            dropoff_zone: 'Contry',
            pay_mxn: 48,
          },
        ],
        nuez: { earnings_mxn: 84.5, deliveries: 2, skipped: 3, cancelled: 1 },
      })
    )
    expect(s.nuez.meta).toMatchObject({
      politica: 'nuez',
      ganado: 84.5,
      entregas: 2,
      rechazos: 3,
      cancelados: 1,
      ofertas_totales: 1,
    })

    const result = { ...s.nuez.meta, ganado: 300, entregas: 9, regreso_en: 112.4 }
    s = applySnapshot(s, snap(120, { status: 'ended', nuez: { result } }))
    expect(s.nuez.meta).toEqual(result)
  })
})

describe('firstDecisionFrom', () => {
  const frames = [
    frame(28),
    frame(29, { decisiones: [decision(29)] }),
    frame(30),
    frame(31, { decisiones: [decision(31, 'aceptar'), decision(31)] }),
  ]

  it('se salta lo de antes del minuto y da la primera en t ≥ minuto', () => {
    const d = firstDecisionFrom(frames, 30)
    expect(d?.t).toBe(31)
    expect(d?.accion).toBe('aceptar')
  })

  it('cuenta el minuto exacto', () => {
    expect(firstDecisionFrom(frames, 29)?.t).toBe(29)
  })

  it('null si todavía no hay ninguna', () => {
    expect(firstDecisionFrom(frames, 32)).toBeNull()
  })
})

describe('countersOf', () => {
  it('lee el bloque del agente, no los frames', () => {
    const s = snap(3, { nuez: { earnings_mxn: 96.35, deliveries: 2, skipped: 4 } })
    expect(countersOf(s.nuez)).toEqual({ ganado: 96.35, entregas: 2, saltadas: 4 })
  })

  it('el último frame acumulado cuadra con earnings_mxn a centavos', () => {
    // Dos entregas en el mismo minuto: un solo frame con el cobro de las dos.
    // contadoresEnT contaría 1 entrega; el bloque del agente dice 2.
    let s = initLiveState(snap(0))
    s = applySnapshot(
      s,
      snap(1, { nuez: { frames: [frame(0, { cobro: 40.1, ganado: 40.1 })], earnings_mxn: 40.1 } })
    )
    const ultimo = snap(2, {
      nuez: {
        frames: [frame(1, { cobro: 56.23, ganado: 96.33 })],
        earnings_mxn: 96.35,
        deliveries: 3,
      },
    })
    s = applySnapshot(s, ultimo)
    const c = countersOf(ultimo.nuez)
    expect(c).toMatchObject({ ganado: 96.35, entregas: 3 })
    expect(Math.abs(s.nuez.frames.at(-1)!.ganado - c.ganado)).toBeLessThanOrEqual(0.05)
  })
})
