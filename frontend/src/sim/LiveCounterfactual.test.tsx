import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { LiveCounterfactualReport as Reporte, LiveCounterfactualState } from '../lib/live'
import { OTRO_TURNO } from '../lib/liveAccum'
import { LiveCounterfactual } from './LiveCounterfactual'

// /live solo pinta el contrafactual que el backend calculó para ESTA sesión. Un reporte de
// otro seed (el grabado de 2000 que antes salía como "referencia") nunca se enseña.
const reporte = (seed: number, session_id: string, order_id: string): Reporte => ({
  session_id,
  seed,
  policy: 'nuez',
  actual: { earned_mxn: 250.4, deliveries: 6, offers: 90, late: false },
  skipped_total: 12,
  money_skips: {
    count: 2,
    evaluated: 2,
    infeasible: 0,
    would_earn_less: 1,
    would_earn_more: 1,
    no_change: 0,
    late_runs: 1,
    cancelled_runs: 0,
    avg_delta_mxn: 3,
    max_gain_mxn: 20.4,
    max_loss_mxn: -14.4,
  },
  safety_skips: { heat_rule: 3 },
  capacity_skips: 2,
  top: [
    {
      order_id,
      minute: 56,
      net_pay_mxn: 42,
      minutes: 22,
      time_value_mxn: 50,
      delta_mxn: 20.4,
      forced_earned_mxn: 270.8,
      forced_deliveries: 7,
      late: true,
      cancelled: 0,
    },
  ],
  note: '',
})

const pintar = (state: LiveCounterfactualState | null, seed = 3141, sessionId = 'live-3141-ab12') =>
  renderToStaticMarkup(
    <LiveCounterfactual state={state} sessionId={sessionId} seed={seed} horaInicio={14} />
  )

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('LiveCounterfactual', () => {
  it('pinta el reporte de esta sesión, con su seed en el título', () => {
    const html = pintar({ status: 'ready', report: reporte(3141, 'live-3141-ab12', 'o_045') })
    expect(html).toContain('If Navie had taken its skips · Seed 3141')
    expect(html).toContain('Skipped 2 for money.')
    expect(html).toContain('14:56 · MXN 42 for 22 min · back late')
    expect(html).toContain('Re-simulated from this live shift')
    expect(html).not.toContain('Recorded')
  })

  it('mientras calcula lo dice, sin números de nadie', () => {
    const html = pintar({ status: 'computing' })
    expect(html).toContain('Seed 3141')
    expect(html).toContain('Re-simulating this shift')
    expect(html).toContain('aria-busy="true"')
    expect(html).not.toContain('MXN')
  })

  it('si falla lo dice tal cual', () => {
    const html = pintar({ status: 'failed', message: 're-simulation failed with ValueError: x' })
    expect(html).toContain(
      'Couldn&#x27;t compute this shift&#x27;s counterfactual: re-simulation failed with ValueError: x'
    )
    expect(html).not.toContain('MXN')
  })

  it('nunca pinta el reporte de otro seed ni de otra sesión, ni cae al grabado', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    for (const ajeno of [
      reporte(2000, 'live-3141-ab12', 'o_seed2000'), // el seed de referencia de antes
      reporte(3141, 'live-3141-zz99', 'o_otra_sesion'),
    ]) {
      const html = pintar({ status: 'ready', report: ajeno })
      expect(html).not.toContain('Seed 2000')
      expect(html).not.toContain(ajeno.top[0].order_id)
      expect(html).not.toContain('Skipped 2 for money.')
      expect(html).not.toContain('MXN')
      expect(html).toContain('Seed 3141')
      expect(html).toContain(OTRO_TURNO.replaceAll("'", '&#x27;'))
    }
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('sin pedirlo todavía no pinta nada', () => {
    expect(pintar(null)).toBe('')
  })
})
