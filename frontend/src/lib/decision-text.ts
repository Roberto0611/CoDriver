// Genera texto en inglés para las decisiones del agente Nuez,
// a partir de los campos `terminos` y `restriccion` del JSON grabado.
// La `razon` del JSON viene en español; esta función la reemplaza.

import type { Decision, Restriccion } from '../contract'

/** Etiqueta legible de cada restricción (inglés, para el chip). */
const RESTRICCION_LABEL: Record<string, string> = {
  flagged_zone_night: 'Flagged zone',
  mandatory_break: 'Mandatory break',
  heat_rule: 'Heat rule',
  shift_end_infeasible: 'Shift ends',
  vehicle_capacity: 'No capacity',
  reservation_wage: 'Below wage',
}

/** De qué tipo es el salto: seguridad, vehículo lleno (límite físico) o dinero. */
export type TipoRestriccion = 'safety' | 'capacity' | 'money'

export function tipoRestriccion(restriccion: Restriccion): TipoRestriccion {
  if (restriccion === 'reservation_wage') return 'money'
  // La capacidad es dura pero no es seguridad: un vehículo lleno no pone en riesgo a nadie.
  if (restriccion === 'vehicle_capacity') return 'capacity'
  return 'safety'
}

/** true si la restricción es de seguridad (ni dinero ni capacidad). */
export function esSeguridad(restriccion: Restriccion | null): boolean {
  return restriccion != null && tipoRestriccion(restriccion) === 'safety'
}

/** Etiqueta corta para la restricción. */
export function etiquetaRestriccion(restriccion: Restriccion | null): string {
  if (!restriccion) return ''
  return RESTRICCION_LABEL[restriccion] ?? restriccion
}

/** Línea principal de la decisión (corta, para la lista). */
export function textoDecisionCorto(d: Decision): string {
  const t = d.terminos
  const pago = t.pago_neto?.toFixed(0) ?? '?'
  const mins = t.minutos?.toFixed(0) ?? '?'

  if (d.accion === 'aceptar') {
    const ventaja = t.ventaja?.toFixed(0) ?? '?'
    return `Accept: MXN ${pago} for ${mins} min (+${ventaja} edge)`
  }

  // Saltar: una restricción dura se nombra; por dinero se enseña la cuenta
  if (d.restriccion && tipoRestriccion(d.restriccion) !== 'money') {
    return `Skip: ${etiquetaRestriccion(d.restriccion)}`
  }

  return `Skip: MXN ${pago} for ${mins} min`
}

/** Detalle expandido de la decisión (los terminos como cuenta legible). */
export function textoDecisionDetalle(d: Decision): string {
  if (d.razon) {
    return d.razon
  }

  const t = d.terminos
  const partes: string[] = []

  // Especial: Mostrar cálculos de fin de turno
  if (
    d.restriccion === 'shift_end_infeasible' &&
    t.minutos_para_terminar != null &&
    t.minutos_de_turno != null
  ) {
    const minsTerminar = t.minutos_para_terminar.toFixed(0)
    const minsTurno = t.minutos_de_turno.toFixed(0)
    return `Takes ${minsTerminar} min to deliver & return. ${minsTurno} min left in shift. No time.`
  }

  if (t.pago_neto != null) partes.push(`Pays MXN ${t.pago_neto.toFixed(0)}`)
  if (t.minutos != null) partes.push(`${t.minutos.toFixed(0)} min`)
  if (t.precio_tiempo != null) {
    partes.push(`those min usually earn MXN ${t.precio_tiempo.toFixed(0)}`)
  }
  if (t.ventaja != null) {
    const abs = Math.abs(t.ventaja).toFixed(0)
    const signo = t.ventaja >= 0 ? '+' : '\u2212'
    partes.push(`edge ${signo}MXN ${abs}`)
  }

  return partes.join(' · ')
}
