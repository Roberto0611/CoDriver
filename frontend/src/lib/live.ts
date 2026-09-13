// Cliente tipado del demo en vivo (/live/* del backend). Los tipos espejan el
// snapshot documentado en backendruta/live_demo.py: los nombres son contrato.
// Cualquier falla sale como LiveApiError con un mensaje que se puede enseñar tal
// cual en el panel; el juez no abre la consola.

import type { Vehiculo } from '../contract'
import { API_URL } from './api'
import type { Frame, Tramo, TurnoMeta } from './turno'

export type AgentKey = 'greedy' | 'nuez'

export interface LiveShock {
  type: 'closure' | 'surge' | 'rain'
  zone: number | null
  zone_name: string | null
  road: string | null
  starts_at_min: number
  ends_at_min: number
  multiplier: number
}

export interface LiveDecision {
  order_id: string
  minute: number
  decision: 'ACCEPT' | 'SKIP'
  reason: string
  binding_constraint: string | null
  terms: Record<string, number>
}

export interface LiveAgent {
  position: number
  /** `[lon, lat]` */
  coords: [number, number]
  earnings_mxn: number
  deliveries: number
  skipped: number
  cancelled: number
  route: { type: string; point: number; order_id: string | null }[]
  last_decision: LiveDecision | null
  /** Deltas: solo llegan en la respuesta de tick. */
  frames: Frame[]
  new_legs: Tramo[]
  geometry: Record<string, [number, number][]>
  /** El `meta` del exportador cuando el turno ya no corre. */
  result: TurnoMeta | null
}

export interface LiveOffer {
  order_id: string
  minute: number
  pickup: number
  dropoff: number
  pickup_zone: string
  dropoff_zone: string
  pay_mxn: number
}

export interface LiveSnapshot {
  session_id: string
  /** El siguiente minuto a correr; [0, minute) ya corrieron. */
  minute: number
  duration_min: number
  start_hour: number
  seed: number
  status: 'running' | 'finished' | 'ended'
  active_shocks: LiveShock[]
  offers_this_tick: LiveOffer[]
  greedy: LiveAgent
  nuez: LiveAgent
  /** Ruta del JSONL; solo la trae /live/end. */
  event_log?: string
}

export interface LiveStartParams {
  seed: number
  duracion_min: number
  hora_inicio: number
  vehiculo: Vehiculo
  /** Id de zona, de GET /zones. */
  ancla: number
  margen_min: number
}

export interface LiveShockBody {
  shock_type: LiveShock['type']
  zone?: number
  duration_min: number
  multiplier?: number
  road?: string
}

export interface LiveZone {
  id: number
  name: string
  lat: number
  lon: number
}

export interface LiveRehearsal {
  seed: number
  closure_minute: number
}

export class LiveApiError extends Error {
  /** 0 = no hubo respuesta (backend caído o sin red). */
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'LiveApiError'
    this.status = status
  }
}

// FastAPI manda `detail` como texto en los HTTPException y como lista de
// errores de pydantic en los 422 de validación.
function textoDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail.map((e) => (e && typeof e === 'object' && 'msg' in e ? String(e.msg) : ''))
    const texto = msgs.filter(Boolean).join('; ')
    return texto || null
  }
  return null
}

async function pedir<T>(path: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new LiveApiError(`Can't reach the live backend at ${API_URL}`, 0)
  }

  if (!res.ok) {
    let detail: string | null = null
    try {
      detail = textoDetail(((await res.json()) as { detail?: unknown }).detail)
    } catch {
      // cuerpo que no es JSON (proxy, 502): se queda el status
    }
    throw new LiveApiError(detail ?? `Live backend answered ${res.status}`, res.status)
  }
  return (await res.json()) as T
}

export function startLive(p: LiveStartParams): Promise<LiveSnapshot> {
  return pedir('/live/start', p)
}

export function tickLive(sessionId: string, minutes = 1): Promise<LiveSnapshot> {
  return pedir('/live/tick', { session_id: sessionId, minutes })
}

export function shockLive(
  sessionId: string,
  body: LiveShockBody
): Promise<{ shock: LiveShock; snapshot: LiveSnapshot }> {
  return pedir('/live/shock', { session_id: sessionId, ...body })
}

export function endLive(sessionId: string): Promise<LiveSnapshot> {
  return pedir('/live/end', { session_id: sessionId })
}

export function getZones(): Promise<LiveZone[]> {
  return pedir('/zones')
}

export function getRehearsal(): Promise<LiveRehearsal> {
  return pedir('/live/rehearsal')
}
