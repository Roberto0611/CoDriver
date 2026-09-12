// Panel de decisiones de Nuez. Más reciente arriba.
// Distingue seguridad (rosa) de dinero (ámbar) con un chip.

import { useState } from 'react'
import { Icon } from '../ui/icons'
import type { Decision } from '../contract'
import type { Frame } from '../lib/turno'
import {
  textoDecisionCorto,
  textoDecisionDetalle,
  etiquetaRestriccion,
  esSeguridad,
} from '../lib/decision-text'
import { minutosAHora } from '../lib/sim'

interface Props {
  frames: Frame[]
  t: number
  horaInicio: number
}

export function Decisions({ frames, t, horaInicio }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Recopilar decisiones hasta el minuto t, más reciente arriba
  const decisiones: (Decision & { minuto: number })[] = []
  for (let i = Math.min(t, frames.length - 1); i >= 0; i--) {
    for (const d of frames[i].decisiones) {
      decisiones.push({ ...d, minuto: i })
    }
  }

  const toggle = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  return (
    <div className="decisions">
      <div className="decisions-title">Nuez Decisions</div>

      {decisiones.length === 0 && (
        <div className="decision-text">No decisions yet…</div>
      )}

      {decisiones.map((d) => {
        const key = `${d.minuto}-${d.oferta_id}`
        const isOpen = expandedId === key
        const isAccept = d.accion === 'aceptar'

        return (
          <div
            key={key}
            className="decision-item"
            onClick={() => toggle(key)}
          >
            <div className="decision-header">
              <span className={`decision-icon ${isAccept ? 'is-accept' : 'is-skip'}`}>
                {isAccept ? Icon.accept : Icon.skip}
              </span>
              <span className="decision-text">{textoDecisionCorto(d)}</span>
              <span className="decision-time num">
                {minutosAHora(horaInicio, d.minuto)}
              </span>
            </div>

            {d.restriccion && (
              <span
                className={`decision-chip ${esSeguridad(d.restriccion) ? 'is-safety' : 'is-money'}`}
              >
                {esSeguridad(d.restriccion) ? Icon.shield : Icon.dollar}
                {etiquetaRestriccion(d.restriccion)}
              </span>
            )}

            {isOpen && (
              <div className="decision-detail">{textoDecisionDetalle(d)}</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
