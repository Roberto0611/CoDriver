// El contrafactual del turno en vivo, bajo el Final Summary. No es el grabado de /sim: el
// backend re-simula ESTA sesión (su seed, su config, los shocks que metió el juez y la
// estrategia con la que Nuez decidió cada pedido) y aquí solo se pinta con el mismo bloque.
// Nunca cae a otro seed: mientras calcula se dice que calcula, y si falla se dice que falló.
// Un turno de 8 h tarda segundos, así que el "calculando" se ve de verdad.

import type { LiveCounterfactualState } from '../lib/live'
import { OTRO_TURNO } from '../lib/liveAccum'
import { CounterfactualReport } from './Counterfactual'

interface Props {
  state: LiveCounterfactualState | null | undefined
  sessionId: string
  seed: number
  horaInicio: number
}

export function LiveCounterfactual({ state, sessionId, seed, horaInicio }: Props) {
  if (!state) return null
  const titulo = `If Navie had taken its skips · Seed ${seed}`

  // Doble guarda: withCounterfactual ya no pega un reporte ajeno, pero este bloque es el
  // que pone "Seed N" en el título, así que tampoco confía en que nadie más lo revisó.
  const propio =
    state.status === 'ready' && state.report.session_id === sessionId && state.report.seed === seed
  if (state.status === 'ready' && propio) {
    return (
      <CounterfactualReport
        datos={state.report}
        horaInicio={horaInicio}
        titulo={titulo}
        nota="Re-simulated from this live shift: same seed, settings, shocks and strategy. Each what-if re-runs it with one order."
      />
    )
  }

  const calculando = state.status === 'computing'
  let texto = OTRO_TURNO
  if (calculando) texto = 'Re-simulating this shift, one skipped order at a time…'
  else if (state.status === 'failed')
    texto = `Couldn't compute this shift's counterfactual: ${state.message}`

  return (
    <div className="turno-summary counterfactual" role="status" aria-busy={calculando}>
      <span className="turno-summary-label">{titulo}</span>
      <p className={calculando ? 'counterfactual-line is-pending' : 'counterfactual-line'}>
        {calculando && <span className="counterfactual-spinner" aria-hidden="true" />}
        {texto}
      </p>
    </div>
  )
}
