// Pila de avisos de decisión de Nuez para el minuto actual: aceptado arriba,
// bloqueado por seguridad abajo.

import { esSeguridad, etiquetaRestriccion } from '../lib/decision-text'
import type { Frame } from '../lib/turno'
import { DecisionToast } from './DecisionToast'

interface Props {
  /** Frame de Nuez en el minuto actual. */
  frame: Frame | undefined
  seed: number | null
  t: number
}

export function DecisionToasts({ frame, seed, t }: Props) {
  const bloqueo = frame?.decisiones.find((d) => d.restriccion && esSeguridad(d.restriccion))
  const aceptado = frame?.decisiones.find((d) => d.accion === 'aceptar')

  const aceptadoTexto = aceptado
    ? `MXN ${aceptado.terminos.pago_neto?.toFixed(0) ?? '?'} for ${aceptado.terminos.minutos?.toFixed(0) ?? '?'} min`
    : null

  return (
    <div className="decision-toast-stack">
      <DecisionToast
        variant="accepted"
        texto={aceptadoTexto}
        decisionKey={aceptado ? `${seed}-${t}-${aceptado.oferta_id}` : null}
      />
      <DecisionToast
        variant="blocked"
        texto={bloqueo?.restriccion ? etiquetaRestriccion(bloqueo.restriccion) : null}
        decisionKey={bloqueo ? `${seed}-${t}-${bloqueo.oferta_id}` : null}
      />
    </div>
  )
}
