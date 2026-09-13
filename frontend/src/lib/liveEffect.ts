// Qué cambió un shock en la ruta de cada agente, contado con datos que ya llegaron.
// No hay contrafactual: no se sabe cuánto habría tardado el tramo sin el cierre, y
// el factor de la física vive en shocks.py. Solo se cuenta lo que pasó de verdad.
//
// La ventana es [starts_at_min, ends_at_min): la misma que `Shock.vigente_en` del
// backend. Un tramo que sale cuando el cierre ya acabó no se estiró por él.

import type { AgentKey } from './live'
import type { LiveShockSeen, LiveState } from './liveAccum'

export type RouteEffect =
  | { kind: 'closure'; zone: string; legs: number; minutes: number }
  | { kind: 'surge'; zone: string; offers: number; accepted: number }

export interface AgentShockEffect {
  /** null si el shock no tiene zona (lluvia) o faltan los puntos para ubicar tramos. */
  route: RouteEffect | null
  /** Pedidos cancelados desde que entró el shock. */
  cancelled: number
}

/** La zona de cada punto del mapa, indexada por `properties.i` de puntos.json. */
export function zonasDePuntos(puntos: GeoJSON.FeatureCollection): string[] {
  const zonas: string[] = []
  for (const f of puntos.features) {
    const { i, zona } = (f.properties ?? {}) as { i?: number; zona?: string }
    if (typeof i === 'number' && typeof zona === 'string') zonas[i] = zona
  }
  return zonas
}

export function efectoShock(
  state: LiveState,
  shock: LiveShockSeen,
  zonaDe: readonly string[]
): Record<AgentKey, AgentShockEffect> {
  const vigente = (t: number) => t >= shock.starts_at_min && t < shock.ends_at_min
  const zona = shock.zone_name

  const deAgente = (a: AgentKey): AgentShockEffect => {
    const cancelled = state.snapshot[a].cancelled - shock.cancelled_at_start[a]
    if (!zona) return { route: null, cancelled }

    if (shock.type === 'closure') {
      // La física estira el tramo si sale o llega a la zona cerrada (factor_tiempo).
      if (zonaDe.length === 0) return { route: null, cancelled }
      const tramos = state[a].tramos.filter(
        (x) => vigente(x.t_salida) && (zonaDe[x.desde] === zona || zonaDe[x.hasta] === zona)
      )
      const minutes = tramos.reduce((suma, x) => suma + (x.t_llegada - x.t_salida), 0)
      return { route: { kind: 'closure', zone: zona, legs: tramos.length, minutes }, cancelled }
    }

    if (shock.type === 'surge') {
      // El surge se cotiza donde nace el pedido (factor_pago usa la zona del pickup).
      const ids = new Set(
        state.offers
          .filter((o) => vigente(o.minute) && o.pickup_zone === zona)
          .map((o) => o.order_id)
      )
      let accepted = 0
      for (const f of state[a].frames) {
        for (const d of f.decisiones) {
          if (d.accion === 'aceptar' && ids.has(d.oferta_id)) accepted++
        }
      }
      return { route: { kind: 'surge', zone: zona, offers: ids.size, accepted }, cancelled }
    }

    return { route: null, cancelled }
  }

  return { greedy: deAgente('greedy'), nuez: deAgente('nuez') }
}
