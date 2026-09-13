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
  order_id: null,
  slip_min: null,
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

describe('shockCopy: restaurante atrasado (delay)', () => {
  // Fuera del minuto ensayado: o_017 en Contry, inyectado a las 14:20.
  const DELAY: LiveShockSeen = {
    ...CIERRE,
    type: 'delay',
    zone: 3,
    zone_name: 'Contry',
    road: null,
    starts_at_min: 20,
    ends_at_min: 120,
    order_id: 'o_017',
    slip_min: 15,
  }
  const sinRuta = (): Record<'greedy' | 'nuez', AgentShockEffect> => ({
    greedy: { route: null, cancelled: 0 },
    nuez: { route: null, cancelled: 0 },
  })

  it('dice qué pedido, dónde recoge y cuánto se atrasa', () => {
    const c = shockCopy(DELAY, sinRuta(), ctx({ minute: 20, lastFrameT: 19 }))
    expect(c.title).toBe('Restaurant running late')
    expect(c.place).toBe('Order o_017, pickup in Contry')
    expect(c.status).toBe('Injected at 14:20, +15 min at the restaurant')
    expect(c.compact).toBe(
      'Restaurant running late · Order o_017, pickup in Contry · +15 min at the restaurant'
    )
  })

  it('pendiente: espera a que se ofrezca ESE pedido, no la siguiente oferta', () => {
    const c = shockCopy(DELAY, sinRuta(), ctx({ minute: 20, lastFrameT: 19 }))
    expect(c.noDecision).toBe('Waiting for order o_017 to be offered…')
    expect(c.coverage).toBeNull()
  })

  it('decidido: sin líneas de tramos ni de ofertas, solo la decisión de cada uno', () => {
    const c = shockCopy(
      DELAY,
      { greedy: { route: null, cancelled: 1 }, nuez: { route: null, cancelled: 0 } },
      ctx({ minute: 22, lastFrameT: 21 })
    )
    expect(c.route).toEqual({ greedy: null, nuez: null })
    expect(c.cancelled.greedy).toBe('1 order cancelled since')
  })

  it('terminado antes de que se ofreciera: honesto, sin waiting', () => {
    const temprano = shockCopy(
      DELAY,
      sinRuta(),
      ctx({ minute: 120, status: 'ended', lastFrameT: 19 })
    )
    expect(temprano.noDecision).toBe("Order o_017 wasn't offered by 14:20")
    expect(temprano.coverage).toBe(
      'Shift ended early at 14:20; legs, offers and decisions count up to 14:20'
    )
    const completo = shockCopy(
      DELAY,
      sinRuta(),
      ctx({ minute: 120, status: 'finished', lastFrameT: 119 })
    )
    expect(completo.noDecision).toBe("Order o_017 wasn't offered before the shift ended")
    expect(todo(temprano) + todo(completo)).not.toMatch(/yet|Waiting/)
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
