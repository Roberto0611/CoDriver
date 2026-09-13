// Traduce `GET /shift/status` al badge y a la nota de Gemini.
// Lógica pura: sin React y sin `fetch` global, para probarla sin red.
//
// Regla: el badge nunca dice "active" si no es cierto. `degraded: false` no basta,
// porque antes de la primera respuesta del modelo también es false; por eso se
// exige además que la estrategia vigente venga de Gemini (`strategy_source`).

export type GeminiState = 'active' | 'degraded' | 'idle'

export interface GeminiView {
  state: GeminiState
  label: string
  /** Nota de la estrategia vigente, o null si no hay nada que enseñar. */
  note: string | null
  /** Texto de la tarjeta cuando `note` es null. */
  placeholder: string
}

/** Lo que devuelve `/shift/status`. Solo los campos que lee el badge. */
export interface ShiftStatus {
  active: boolean
  degraded?: boolean
  strategy_source?: string | null
  strategy_note?: string | null
  /** false después de /shift/end: el backend conserva el turno, pero ya no está vivo. */
  strategy_running?: boolean
}

export const POLL_MS = 3000
/** Tope del backoff con el backend apagado. */
export const POLL_OFFLINE_MAX_MS = 60000
export const TIMEOUT_MS = 2500

const SIN_TURNO = 'No live shift. Notes appear when Gemini updates the strategy.'
const SIN_NOTA = 'Shift is live. No note from Gemini yet.'
const CAIDO = 'Gemini is not answering. The engine keeps deciding on its last strategy.'

export const GEMINI_IDLE: GeminiView = {
  state: 'idle',
  label: 'Gemini: idle',
  note: null,
  placeholder: SIN_TURNO,
}

function esEstado(valor: unknown): valor is ShiftStatus {
  return typeof valor === 'object' && valor !== null && 'active' in valor
}

function limpiarNota(nota: unknown): string | null {
  if (typeof nota !== 'string') return null
  const recortada = nota.trim()
  return recortada === '' ? null : recortada
}

/** Respuesta de `/shift/status` (ya parseada, de forma desconocida) → vista del badge. */
export function vistaGemini(respuesta: unknown): GeminiView {
  if (!esEstado(respuesta) || respuesta.active !== true) return GEMINI_IDLE
  // Turno cerrado: `active` sigue en true, pero la capa ya no corre. Nada de "Shift is live".
  if (respuesta.strategy_running === false) return GEMINI_IDLE

  const note = limpiarNota(respuesta.strategy_note)
  if (respuesta.degraded === true) {
    return {
      state: 'degraded',
      label: 'Gemini: down, using last strategy',
      note,
      placeholder: CAIDO,
    }
  }
  if (respuesta.strategy_source === 'gemini') {
    return { state: 'active', label: 'Gemini: active', note, placeholder: SIN_NOTA }
  }
  // Turno vivo, pero la estrategia es la base (aún sin respuesta) o el suplente
  // local: Gemini no está hablando, así que ni badge verde ni su nota.
  return { ...GEMINI_IDLE, placeholder: SIN_NOTA }
}

/** Dos vistas iguales no vuelven a pintar el badge. */
export function mismaVista(a: GeminiView, b: GeminiView): boolean {
  return (
    a.state === b.state &&
    a.label === b.label &&
    a.note === b.note &&
    a.placeholder === b.placeholder
  )
}

export interface Consulta {
  view: GeminiView
  /** false si el backend no contestó (apagado, timeout, HTTP de error, JSON roto). */
  reachable: boolean
}

/**
 * Cada cuánto volver a preguntar, según cuántas consultas seguidas no llegaron.
 * Con el backend apagado el navegador anota un error de red por cada intento (eso
 * no se puede callar desde JS), así que la espera se duplica hasta un minuto: 3 s,
 * 6 s, 12 s… Un solo fallo pasajero no apaga el badge; al volver, regresa a 3 s.
 */
export function esperaTrasConsulta(fallosSeguidos: number): number {
  if (fallosSeguidos <= 0) return POLL_MS
  return Math.min(POLL_OFFLINE_MAX_MS, POLL_MS * 2 ** fallosSeguidos)
}

type Fetcher = (
  url: string,
  init: { signal: AbortSignal }
) => Promise<Pick<Response, 'ok' | 'json'>>

/** Una consulta. Nunca rechaza: cualquier tropiezo termina en idle. */
export async function consultarGemini(
  fetcher: Fetcher,
  apiUrl: string,
  signal: AbortSignal
): Promise<Consulta> {
  try {
    const respuesta = await fetcher(`${apiUrl}/shift/status`, { signal })
    if (!respuesta.ok) return { view: GEMINI_IDLE, reachable: false }
    return { view: vistaGemini(await respuesta.json()), reachable: true }
  } catch {
    return { view: GEMINI_IDLE, reachable: false }
  }
}
