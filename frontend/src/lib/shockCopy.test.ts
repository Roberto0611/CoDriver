import { describe, it, expect } from 'vitest'

import type { LiveShockSeen } from './liveAccum'
import type { AgentShockEffect } from './liveEffect'
import { shockCopy, type ShockCopyContext } from './shockCopy'

const CIERRE: LiveShockSeen = {
  type: 'closure',
  zone: 0,
  zone_name: 'Centro',
  road: 'Constitución',
  starts_at_min: 30,
  ends_at_min: 70,
  multiplier: 1,
  cancelled_at_start: { greedy: 0, nuez: 0 },
}

const SURGE: LiveShockSeen = {
  ...CIERRE,
  type: 'surge',
  zone: 4,
  zone_name: 'Tec',
  road: null,
  starts_at_min: 50,
  ends_at_min: 80,
  multiplier: 1.8,
}

const sinTramos = (): Record<'greedy' | 'nuez', AgentShockEffect> => ({
  greedy: { route: { kind: 'closure', zone: 'Centro', legs: 0, minutes: 0 }, cancelled: 0 },
  nuez: { route: { kind: 'closure', zone: 'Centro', legs: 0, minutes: 0 }, cancelled: 0 },
})

const ctx = (c: Partial<ShockCopyContext>): ShockCopyContext => ({
  minute: 35,
  durationMin: 120,
  startHour: 14,
  status: 'running',
  lastFrameT: 34,
  ...c,
})

// Todo el texto que produce, para buscar copy prohibido de una vez.
const todo = (c: ReturnType<typeof shockCopy>) =>
  [c.status, c.coverage, c.noDecision, ...Object.values(c.route), ...Object.values(c.cancelled)]
    .filter(Boolean)
    .join(' | ')

describe('shockCopy: turno corriendo', () => {
  it('habla de lo que falta: active until, yet, waiting', () => {
    const c = shockCopy(CIERRE, sinTramos(), ctx({}))
    expect(c.status).toBe('Injected at 14:30, active until 15:10')
    expect(c.coverage).toBeNull()
    expect(c.route.nuez).toBe('No legs through Centro yet')
    expect(c.noDecision).toBe('Waiting for the next offer…')
  })

  it('dice ended at cuando el shock ya expiró', () => {
    const c = shockCopy(CIERRE, sinTramos(), ctx({ minute: 75, lastFrameT: 74 }))
    expect(c.status).toBe('Injected at 14:30, ended at 15:10')
  })

  it('cuenta tramos, ofertas y cancelados con plural', () => {
    const c = shockCopy(
      SURGE,
      {
        greedy: { route: { kind: 'surge', zone: 'Tec', offers: 2, accepted: 1 }, cancelled: 1 },
        nuez: { route: { kind: 'closure', zone: 'Centro', legs: 1, minutes: 6.4 }, cancelled: 2 },
      },
      ctx({ minute: 60, lastFrameT: 59 })
    )
    expect(c.route.greedy).toBe('2 offers from Tec, took 1')
    expect(c.route.nuez).toBe('1 leg through Centro, 6 min')
    expect(c.cancelled.greedy).toBe('1 order cancelled since')
    expect(c.cancelled.nuez).toBe('2 orders cancelled since')
  })

  it('sin efecto de ruta ni cancelados no hay línea', () => {
    const c = shockCopy(
      CIERRE,
      { greedy: { route: null, cancelled: 0 }, nuez: { route: null, cancelled: 0 } },
      ctx({})
    )
    expect(c.route).toEqual({ greedy: null, nuez: null })
    expect(c.cancelled).toEqual({ greedy: null, nuez: null })
  })
})

describe('shockCopy: terminado antes de tiempo (End a media corrida)', () => {
  const temprano = ctx({ minute: 120, status: 'ended', lastFrameT: 61 })

  it('avisa hasta dónde cuentan los números', () => {
    const c = shockCopy(CIERRE, sinTramos(), temprano)
    expect(c.coverage).toBe(
      'Shift ended early at 15:02; legs, offers and decisions count up to 15:02'
    )
  })

  it('cambia yet por none y waiting por no offer', () => {
    const c = shockCopy(CIERRE, sinTramos(), temprano)
    expect(c.route.nuez).toBe('Legs through Centro: none')
    expect(c.noDecision).toBe('No offer before the shift ended')
    const surge = shockCopy(
      SURGE,
      {
        greedy: { route: { kind: 'surge', zone: 'Tec', offers: 0, accepted: 0 }, cancelled: 0 },
        nuez: { route: null, cancelled: 0 },
      },
      temprano
    )
    expect(surge.route.greedy).toBe('Offers from Tec: none')
    expect(todo(c) + todo(surge)).not.toMatch(/yet|Waiting/)
  })

  it('el backend sí corrió el resto: el cierre terminó a su hora', () => {
    expect(shockCopy(CIERRE, sinTramos(), temprano).status).toBe(
      'Injected at 14:30, ended at 15:10'
    )
  })
})

describe('shockCopy: terminado completo', () => {
  it('sin aviso de cobertura y sin copy de espera', () => {
    for (const status of ['finished', 'ended'] as const) {
      const c = shockCopy(CIERRE, sinTramos(), ctx({ minute: 120, status, lastFrameT: 119 }))
      expect(c.coverage).toBeNull()
      expect(c.noDecision).toBe('No offer before the shift ended')
      expect(c.route.greedy).toBe('Legs through Centro: none')
      expect(todo(c)).not.toMatch(/yet|Waiting/)
    }
  })
})

describe('shockCopy: shock que dura más que el turno', () => {
  const largo = { ...SURGE, starts_at_min: 100, ends_at_min: 130 }

  it('no da una hora después de las 16:00', () => {
    expect(shockCopy(largo, sinTramos(), ctx({ minute: 105, lastFrameT: 104 })).status).toBe(
      'Injected at 15:40, active until the end of the shift'
    )
    expect(
      shockCopy(largo, sinTramos(), ctx({ minute: 120, status: 'ended', lastFrameT: 119 })).status
    ).toBe('Injected at 15:40, active until the end of the shift')
  })

  it('la línea compacta de un shock anterior tampoco', () => {
    const c = shockCopy(largo, sinTramos(), ctx({ minute: 105, lastFrameT: 104 }))
    expect(c.compact).toBe('Surge ×1.8 · Tec · active until the end of the shift')
  })
})
