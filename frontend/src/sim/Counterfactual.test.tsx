import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { Contrafactual } from '../lib/contrafactual'
import { CounterfactualReport } from './Counterfactual'

// El reporte que pinta /live al terminar: el mismo bloque que /sim, con datos que ya llegaron.
const REPORTE: Contrafactual = {
  seed: 2005,
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
  safety_skips: { heat_rule: 3, shift_end_infeasible: 0 },
  capacity_skips: 2,
  top: [
    {
      order_id: 'o_045',
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
}

describe('CounterfactualReport', () => {
  it('pinta los saltos por dinero, cada pedido con su hora y los bloqueos sin precio', () => {
    const html = renderToStaticMarkup(<CounterfactualReport datos={REPORTE} horaInicio={14} />)
    expect(html).toContain('If Navie had taken its skips')
    expect(html).toContain('Skipped 2 for money.')
    expect(html).toContain('14:56 · MXN 42 for 22 min · back late')
    expect(html).toContain('+MXN 20')
    expect(html).toContain('Heat rule 3')
    expect(html).toContain('Vehicle full:')
  })
})
