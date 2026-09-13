// El texto del banner del shock, separado del componente para poder probar que
// nunca miente. Dos trampas que cuida:
//
// 1. /live/end adelanta hasta el final sin mandar frames, tramos ni ofertas. Si el
//    juez termina a media corrida, lo que el banner cuenta se queda en el último
//    minuto que sí se pidió. Hay que decirlo, y no dejar "yet" ni "Waiting…" en una
//    sesión que ya no va a recibir nada.
// 2. Un shock puede durar más que el turno. Una hora después de las 16:00 en un
//    turno que acaba a las 16:00 no significa nada.

import type { AgentKey, LiveSnapshot } from './live'
import type { LiveShockSeen } from './liveAccum'
import type { AgentShockEffect } from './liveEffect'
import { minutosAHora } from './sim'

export interface ShockCopyContext {
  /** `snapshot.minute`: el siguiente minuto a correr. */
  minute: number
  durationMin: number
  startHour: number
  status: LiveSnapshot['status']
  /** `t` del último frame acumulado; -1 si todavía no hay ninguno. */
  lastFrameT: number
}

export interface ShockCopy {
  title: string
  place: string
  /** "Injected at 14:30, active until 15:10" */
  status: string
  /** Solo si el turno terminó antes de pedir todos sus minutos. */
  coverage: string | null
  route: Record<AgentKey, string | null>
  cancelled: Record<AgentKey, string | null>
  /** Lo que va en lugar de la decisión cuando no hubo ninguna. */
  noDecision: string
  /** Una línea, para los shocks anteriores. */
  compact: string
}

const plural = (n: number, una: string, varias: string) => `${n} ${n === 1 ? una : varias}`

function titulo(s: LiveShockSeen): string {
  if (s.type === 'closure') return 'Road closure'
  if (s.type === 'surge') return `Surge ×${s.multiplier.toFixed(1)}`
  return 'Rain'
}

function lugar(s: LiveShockSeen): string {
  if (s.road && s.zone_name) return `${s.road}, ${s.zone_name}`
  return s.road ?? s.zone_name ?? 'Whole city'
}

function vigencia(s: LiveShockSeen, c: ShockCopyContext): string {
  if (s.ends_at_min >= c.durationMin) return 'active until the end of the shift'
  const hora = minutosAHora(c.startHour, s.ends_at_min)
  return c.minute >= s.ends_at_min ? `ended at ${hora}` : `active until ${hora}`
}

function ruta(e: AgentShockEffect, terminado: boolean): string | null {
  const r = e.route
  if (!r) return null
  if (r.kind === 'closure') {
    if (r.legs > 0) {
      return `${plural(r.legs, 'leg', 'legs')} through ${r.zone}, ${r.minutes.toFixed(0)} min`
    }
    return terminado ? `Legs through ${r.zone}: none` : `No legs through ${r.zone} yet`
  }
  if (r.offers > 0)
    return `${plural(r.offers, 'offer', 'offers')} from ${r.zone}, took ${r.accepted}`
  return terminado ? `Offers from ${r.zone}: none` : `No offers from ${r.zone} yet`
}

/** La línea compacta de un shock anterior. */
export function shockLine(shock: LiveShockSeen, c: ShockCopyContext): string {
  return `${titulo(shock)} · ${lugar(shock)} · ${vigencia(shock, c)}`
}

export function shockCopy(
  shock: LiveShockSeen,
  effects: Record<AgentKey, AgentShockEffect>,
  c: ShockCopyContext
): ShockCopy {
  const terminado = c.status !== 'running'
  // Los frames cubren [0, lastFrameT]; el turno pidió hasta ahí y lo demás lo adelantó /live/end.
  const corte = c.lastFrameT + 1
  const temprano = terminado && corte < c.durationMin
  const horaCorte = minutosAHora(c.startHour, corte)
  const cancelado = (a: AgentKey) =>
    effects[a].cancelled > 0
      ? `${plural(effects[a].cancelled, 'order', 'orders')} cancelled since`
      : null

  return {
    title: titulo(shock),
    place: lugar(shock),
    status: `Injected at ${minutosAHora(c.startHour, shock.starts_at_min)}, ${vigencia(shock, c)}`,
    coverage: temprano
      ? `Shift ended early at ${horaCorte}; legs, offers and decisions count up to ${horaCorte}`
      : null,
    route: { greedy: ruta(effects.greedy, terminado), nuez: ruta(effects.nuez, terminado) },
    cancelled: { greedy: cancelado('greedy'), nuez: cancelado('nuez') },
    noDecision: terminado ? 'No offer before the shift ended' : 'Waiting for the next offer…',
    compact: shockLine(shock, c),
  }
}
