import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  cargarContrafactual,
  esContrafactual,
  formatoDelta,
  lineaDinero,
  lineaPedido,
  lineaSeguridad,
  type Contrafactual,
  type SaltosPorDinero,
} from './contrafactual'

function dinero(cambios: Partial<SaltosPorDinero> = {}): SaltosPorDinero {
  return {
    count: 0,
    evaluated: 0,
    infeasible: 0,
    would_earn_less: 0,
    would_earn_more: 0,
    no_change: 0,
    late_runs: 0,
    cancelled_runs: 0,
    avg_delta_mxn: null,
    max_gain_mxn: null,
    max_loss_mxn: null,
    ...cambios,
  }
}

function reporte(seed: number): Contrafactual {
  return {
    seed,
    policy: 'nuez',
    actual: { earned_mxn: 309.5, deliveries: 7, offers: 96, late: false },
    skipped_total: 89,
    money_skips: dinero({ count: 2, evaluated: 2, would_earn_less: 2, max_loss_mxn: -41.85 }),
    safety_skips: { heat_rule: 23, shift_end_infeasible: 23 },
    capacity_skips: 41,
    top: [],
    note: '',
  }
}

describe('formatoDelta', () => {
  it('positivo lleva +', () => {
    expect(formatoDelta(34.69)).toBe('+MXN 35')
  })

  it('negativo lleva el signo menos tipográfico', () => {
    expect(formatoDelta(-41.85)).toBe('−MXN 42')
  })

  it('lo que redondea a cero no lleva signo', () => {
    expect(formatoDelta(0.4)).toBe('MXN 0')
    expect(formatoDelta(-0.4)).toBe('MXN 0')
  })
})

describe('lineaDinero', () => {
  it('sin saltos por dinero', () => {
    expect(lineaDinero(dinero())).toBe('Skipped nothing for money.')
  })

  it('uno solo que habría ganado más', () => {
    expect(
      lineaDinero(dinero({ count: 1, evaluated: 1, would_earn_more: 1, max_gain_mxn: 34.69 }))
    ).toBe('Skipped 1 for money. Taking it would have earned MXN 35 more.')
  })

  it('uno solo que habría ganado menos', () => {
    expect(
      lineaDinero(dinero({ count: 1, evaluated: 1, would_earn_less: 1, max_loss_mxn: -7.9 }))
    ).toBe('Skipped 1 for money. Taking it would have earned MXN 8 less.')
  })

  it('varios: cuenta cuántos ganan menos y más, con el mejor, sin total', () => {
    const texto = lineaDinero(
      dinero({
        count: 62,
        evaluated: 62,
        would_earn_less: 48,
        would_earn_more: 14,
        max_gain_mxn: 12.2,
        max_loss_mxn: -50,
      })
    )
    expect(texto).toBe(
      'Skipped 62 for money. Taking any single one: 48 would have earned less, 14 more (best +MXN 12).'
    )
    expect(texto).not.toMatch(/total/i)
  })

  it('varios sin ninguno mejor no inventa un "best"', () => {
    expect(
      lineaDinero(dinero({ count: 2, evaluated: 2, would_earn_less: 2, max_loss_mxn: -41.85 }))
    ).toBe('Skipped 2 for money. Taking any single one: 2 would have earned less, 0 more.')
  })

  it('los que una regla dura bloqueó al forzarlos se dicen aparte', () => {
    expect(lineaDinero(dinero({ count: 1, infeasible: 1 }))).toBe(
      'Skipped 1 for money. 1 still blocked by a hard rule when forced.'
    )
  })
})

describe('lineaSeguridad', () => {
  it('solo las restricciones que mordieron, con la etiqueta de siempre', () => {
    expect(lineaSeguridad({ flagged_zone_night: 0, heat_rule: 23, shift_end_infeasible: 32 })).toBe(
      'Heat rule 23 · Shift ends 32'
    )
  })

  it('sin bloqueos queda vacío', () => {
    expect(lineaSeguridad({ heat_rule: 0 })).toBe('')
  })
})

describe('lineaPedido', () => {
  it('hora de reloj, pago neto y minutos redondeados', () => {
    expect(
      lineaPedido(
        {
          order_id: 'o_033',
          minute: 48,
          net_pay_mxn: 42.3,
          minutes: 22.3,
          time_value_mxn: 64.2,
          delta_mxn: -41.85,
          forced_earned_mxn: 267.65,
          forced_deliveries: 6,
          late: false,
          cancelled: 0,
        },
        14
      )
    ).toBe('14:48 · MXN 42 for 22 min')
  })
})

describe('esContrafactual', () => {
  it('acepta la forma grabada', () => {
    expect(esContrafactual(reporte(2000))).toBe(true)
  })

  it('rechaza lo que no es', () => {
    expect(esContrafactual(null)).toBe(false)
    expect(esContrafactual('<!doctype html>')).toBe(false)
    expect(esContrafactual({ seed: 2000 })).toBe(false)
  })

  it('rechaza un archivo viejo, con la capacidad metida en safety_skips', () => {
    const { capacity_skips: _, ...viejo } = reporte(2000)
    expect(esContrafactual(viejo)).toBe(false)
  })
})

describe('cargarContrafactual', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('404 → null', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('', { status: 404 }))
    )
    expect(await cargarContrafactual(9001)).toBeNull()
  })

  it('HTML con 200 → null', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<!doctype html>', { status: 200 }))
    )
    expect(await cargarContrafactual(9002)).toBeNull()
  })

  it('red caída → null, y no se queda recordado', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('offline')
      })
    )
    expect(await cargarContrafactual(9003)).toBeNull()

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json(reporte(9003)))
    )
    expect((await cargarContrafactual(9003))?.seed).toBe(9003)
  })

  it('un seed que no coincide → null', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Response.json(reporte(1)))
    )
    expect(await cargarContrafactual(9004)).toBeNull()
  })

  it('carga, y la segunda vez sale del cache', async () => {
    const fetchMock = vi.fn(async () => Response.json(reporte(9005)))
    vi.stubGlobal('fetch', fetchMock)
    expect((await cargarContrafactual(9005))?.money_skips.count).toBe(2)
    expect((await cargarContrafactual(9005))?.seed).toBe(9005)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/contrafactual_9005.json')
  })
})
