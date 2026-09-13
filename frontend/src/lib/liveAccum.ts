// Acumulador del demo en vivo: junta los snapshots del backend en dos TurnoData,
// la misma forma que pinta el replay grabado, para reusar mapa, estelas y paneles.
//
// frames, new_legs y geometry llegan como deltas (solo en tick), así que aquí se
// pegan; lo demás del snapshot es el estado completo y se reemplaza. La geometría
// va por agente porque el backend deduplica por agente: juntarla en un solo mapa
// funcionaría hoy por casualidad.

import type { ConfigTurno, Decision, Vehiculo } from '../contract'
import type {
  AgentKey,
  LiveAgent,
  LiveCounterfactualState,
  LiveOffer,
  LiveShock,
  LiveSnapshot,
} from './live'
import type { Contadores } from './sim'
import type { Frame, TurnoData, TurnoMeta } from './turno'

/** Un shock ya visto, con los cancelados de cada agente cuando apareció. */
export interface LiveShockSeen extends LiveShock {
  cancelled_at_start: Record<AgentKey, number>
}

export interface LiveState {
  snapshot: LiveSnapshot
  greedy: TurnoData
  nuez: TurnoData
  /** Todos los shocks vistos en la sesión, incluidos los que ya expiraron. */
  shocks: LiveShockSeen[]
  /** Todas las ofertas que aparecieron, para medir qué hizo un surge. */
  offers: LiveOffer[]
  /** El contrafactual de la sesión terminada; null mientras nadie lo ha pedido.
   *  Opcional para que un LiveState armado a mano (los tests del banner) siga valiendo. */
  counterfactual?: LiveCounterfactualState | null
}

/** Lo que el snapshot no trae pero el config sí pide. */
export interface LiveConfigExtra {
  vehiculo?: Vehiculo
  margen_min?: number
}

const AGENTES: AgentKey[] = ['greedy', 'nuez']

function metaEnVivo(politica: AgentKey, snap: LiveSnapshot, ofertasTotales: number): TurnoMeta {
  const a = snap[politica]
  if (a.result) return a.result
  return {
    politica,
    seed: snap.seed,
    ganado: a.earnings_mxn,
    entregas: a.deliveries,
    rechazos: a.skipped,
    ofertas_totales: ofertasTotales,
    violaciones: 0,
    llego_tarde: false,
    regreso_en: 0,
    cancelados: a.cancelled,
  }
}

// Con el pedido: dos delays en el mismo minuto a pedidos distintos son dos shocks.
function claveShock(s: LiveShock): string {
  return `${s.type}|${s.zone}|${s.road}|${s.starts_at_min}|${s.ends_at_min}|${s.multiplier}|${s.order_id}`
}

export function initLiveState(snap: LiveSnapshot, extra: LiveConfigExtra = {}): LiveState {
  // Al arrancar los dos están en el ancla: su posición es el ancla del config,
  // que es donde posicionEnMinuto pinta la moto antes del primer tramo.
  const armar = (politica: AgentKey): TurnoData => {
    const [lon, lat] = snap[politica].coords
    const config: ConfigTurno = {
      duracion_min: snap.duration_min,
      ancla: { nombre: '', lat, lon },
      margen_min: extra.margen_min ?? 10,
      vehiculo: extra.vehiculo ?? 'moto',
      seed: snap.seed,
      hora_inicio: snap.start_hour,
      // /live/start no lo expone: el turno en vivo usa el default del motor y regresa al ancla.
      regresar_al_ancla: true,
    }
    return {
      meta: metaEnVivo(politica, snap, 0),
      config,
      tramos: [],
      geometria: {},
      frames: [],
    }
  }
  return applySnapshot(
    {
      snapshot: snap,
      greedy: armar('greedy'),
      nuez: armar('nuez'),
      shocks: [],
      offers: [],
      counterfactual: null,
    },
    snap
  )
}

function acumular(
  prev: TurnoData,
  politica: AgentKey,
  snap: LiveSnapshot,
  ofertasTotales: number
): TurnoData {
  const a: LiveAgent = snap[politica]
  const vistos = prev.frames.at(-1)?.t ?? -1
  // Un frame repetido rompería el índice frames[t] que usan las llegadas del mapa.
  const nuevos = a.frames.filter((f) => f.t > vistos)
  return {
    meta: metaEnVivo(politica, snap, ofertasTotales),
    config: {
      ...prev.config,
      duracion_min: snap.duration_min,
      hora_inicio: snap.start_hour,
      seed: snap.seed,
    },
    tramos: a.new_legs.length ? [...prev.tramos, ...a.new_legs] : prev.tramos,
    geometria: Object.keys(a.geometry).length
      ? { ...prev.geometria, ...a.geometry }
      : prev.geometria,
    frames: nuevos.length ? [...prev.frames, ...nuevos] : prev.frames,
  }
}

export function applySnapshot(prev: LiveState, snap: LiveSnapshot): LiveState {
  const offers = snap.offers_this_tick.length
    ? [...prev.offers, ...snap.offers_this_tick]
    : prev.offers
  const [greedy, nuez] = AGENTES.map((a) => acumular(prev[a], a, snap, offers.length))

  // El banner no se va cuando el shock expira: se guarda todo lo que se vio.
  const conocidos = new Set(prev.shocks.map(claveShock))
  const nuevos = snap.active_shocks
    .filter((s) => !conocidos.has(claveShock(s)))
    .map((s) => ({
      ...s,
      cancelled_at_start: { greedy: snap.greedy.cancelled, nuez: snap.nuez.cancelled },
    }))

  return {
    snapshot: snap,
    greedy,
    nuez,
    shocks: nuevos.length ? [...prev.shocks, ...nuevos] : prev.shocks,
    offers,
    counterfactual: prev.counterfactual,
  }
}

/** Lo que se enseña si el backend contesta con el reporte de otro turno. */
export const OTRO_TURNO =
  "The backend answered with another shift's counterfactual, so it isn't shown."

/**
 * Pone el estado del contrafactual que se pidió al terminar. Solo en ESTA sesión y ya
 * terminada: la respuesta de una sesión soltada que llega tarde no toca la vigente. Un
 * reporte de otra sesión u otro seed nunca se pega: queda como falla, dicha tal cual, en
 * vez de un "calculando" eterno o de números de otro turno bajo el título de este.
 */
export function withCounterfactual(
  state: LiveState,
  sessionId: string,
  next: LiveCounterfactualState
): LiveState {
  const s = state.snapshot
  if (s.session_id !== sessionId || s.status === 'running') return state
  const ajeno =
    next.status === 'ready' && (next.report.session_id !== sessionId || next.report.seed !== s.seed)
  return {
    ...state,
    counterfactual: ajeno ? { status: 'failed', message: OTRO_TURNO } : next,
  }
}

/** La primera decisión en un minuto ≥ `minute`: la reacción al shock. */
export function firstDecisionFrom(frames: Frame[], minute: number): Decision | null {
  for (const f of frames) {
    if (f.t >= minute && f.decisiones.length > 0) return f.decisiones[0]
  }
  return null
}

/** Contadores del bloque del agente. No se recalculan de los frames: dos entregas
 *  en el mismo minuto son un solo frame y el ganado de los frames se redondea. */
export function countersOf(agent: LiveAgent): Contadores {
  return { ganado: agent.earnings_mxn, entregas: agent.deliveries, saltadas: agent.skipped }
}
