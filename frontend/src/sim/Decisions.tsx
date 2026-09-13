// Panel de decisiones de Nuez. Más reciente arriba.
// Distingue con un chip seguridad (rosa), vehículo lleno (neutro) y dinero (ámbar).

import { useState, type ReactNode } from 'react'
import { Icon } from '../ui/icons'
import type { Decision, Restriccion } from '../contract'
import type { Frame } from '../lib/turno'
import {
  textoDecisionCorto,
  textoDecisionDetalle,
  etiquetaRestriccion,
  tipoRestriccion,
  type TipoRestriccion,
} from '../lib/decision-text'
import { minutosAHora } from '../lib/sim'

const CHIP_ICON: Record<TipoRestriccion, ReactNode> = {
  safety: Icon.shield,
  capacity: Icon.box,
  money: Icon.dollar,
}

/** El chip de la restricción; también lo usa el banner del shock en vivo. */
export function RestriccionChip({ restriccion }: { restriccion: Restriccion }) {
  const tipo = tipoRestriccion(restriccion)
  return (
    <span className={`decision-chip is-${tipo}`}>
      {CHIP_ICON[tipo]}
      {etiquetaRestriccion(restriccion)}
    </span>
  )
}

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

      {decisiones.length === 0 && <div className="decision-text">No decisions yet…</div>}

      {decisiones.map((d) => {
        const key = `${d.minuto}-${d.oferta_id}`
        const isOpen = expandedId === key
        const isAccept = d.accion === 'aceptar'

        return (
          <div key={key} className="decision-item" onClick={() => toggle(key)}>
            <div className="decision-header">
              <span className={`decision-icon ${isAccept ? 'is-accept' : 'is-skip'}`}>
                {isAccept ? Icon.accept : Icon.skip}
              </span>
              <span className="decision-text">{textoDecisionCorto(d)}</span>
              <span className="decision-time num">{minutosAHora(horaInicio, d.minuto)}</span>
            </div>

            {d.restriccion && <RestriccionChip restriccion={d.restriccion} />}

            {isOpen && <div className="decision-detail">{textoDecisionDetalle(d)}</div>}
          </div>
        )
      })}
    </div>
  )
}
