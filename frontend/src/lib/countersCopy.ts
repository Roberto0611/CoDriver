// Copy del contador y del resumen final. Vive aparte para probarlo sin montar
// React y porque /sim y /live comparten el mismo componente.

import type { ConfigTurno } from '../contract'

/** Lo único del config que hace falta para saber a qué hora hay que estar de vuelta. */
export type ConfigRegreso = Pick<ConfigTurno, 'hora_inicio' | 'duracion_min' | 'margen_min'> &
  Partial<Pick<ConfigTurno, 'regresar_al_ancla'>>

/**
 * El renglón del resumen final. Con `regresar_al_ancla` (el default del motor y de
 * los turnos grabados) la línea es volver al ancla; sin él, sim.py solo exige
 * terminar la última entrega antes de esa misma hora, así que no se dice "Back".
 */
export function renglonDeRegreso(config: ConfigRegreso): string {
  const hora = horaDeRegreso(config)
  return config.regresar_al_ancla === false ? `Deliveries done by ${hora}` : `Back by ${hora}`
}

/**
 * La hora de reloj en que el repartidor tiene que estar en el ancla: inicio +
 * duración − margen. La línea es esa y no el fin del turno (sim.py lo dice igual:
 * volver en el 115 de 120 con margen 10 es llegar tarde). Da la vuelta a la
 * medianoche porque un turno de 8 h que arranca de noche existe.
 */
export function horaDeRegreso({ hora_inicio, duracion_min, margen_min }: ConfigRegreso): string {
  const minutos = (((hora_inicio * 60 + duracion_min - margen_min) % 1440) + 1440) % 1440
  const hh = Math.floor(minutos / 60)
  const mm = Math.round(minutos % 60)
  return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`
}

/** "1 delivery", "0 deliveries". El juez sí lee el "1 deliveries". */
export function entregasTexto(n: number): string {
  return `${n} ${n === 1 ? 'delivery' : 'deliveries'}`
}
