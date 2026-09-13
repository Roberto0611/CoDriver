// Badge de Gemini (junto al logo) y tarjeta con su última nota de estrategia.
// Ambos leen la misma consulta a `GET /shift/status`: un solo sondeo compartido,
// que arranca con el primer componente montado y se apaga con el último.

import { useSyncExternalStore } from 'react'

import { API_URL } from '../lib/api'
import {
  consultarGemini,
  esperaTrasConsulta,
  GEMINI_IDLE,
  mismaVista,
  TIMEOUT_MS,
  type GeminiView,
} from '../lib/gemini-status'
import '../styles/gemini.css'

let vista: GeminiView = GEMINI_IDLE
const oyentes = new Set<() => void>()
// Cada arranque tiene su número; una respuesta de un sondeo ya apagado se tira.
let ronda = 0
let espera: ReturnType<typeof setTimeout> | undefined
let enCurso: AbortController | null = null
// Consultas seguidas sin respuesta: con el backend apagado, cada una ensucia la consola.
let fallos = 0

function sondear(mia: number) {
  // Con la pestaña oculta no se pregunta; `alVolverALaPestana` retoma al verse otra vez.
  if (document.hidden) return
  const control = new AbortController()
  enCurso = control
  const limite = setTimeout(() => control.abort(), TIMEOUT_MS)
  // Se encadena con setTimeout al terminar, no con setInterval: nunca hay dos a la vez.
  void consultarGemini((url, init) => fetch(url, init), API_URL, control.signal).then(
    ({ view, reachable }) => {
      clearTimeout(limite)
      if (mia !== ronda || enCurso !== control) return
      enCurso = null
      fallos = reachable ? 0 : fallos + 1
      if (!mismaVista(view, vista)) {
        vista = view
        oyentes.forEach((avisar) => avisar())
      }
      espera = setTimeout(() => sondear(mia), esperaTrasConsulta(fallos))
    }
  )
}

/** Al volver a la pestaña se pregunta ya, sin esperar lo que quedaba del backoff. */
function alVolverALaPestana() {
  if (document.hidden || enCurso) return
  clearTimeout(espera)
  sondear(ronda)
}

function suscribir(avisar: () => void) {
  oyentes.add(avisar)
  if (oyentes.size === 1) {
    document.addEventListener('visibilitychange', alVolverALaPestana)
    sondear(++ronda)
  }
  return () => {
    oyentes.delete(avisar)
    if (oyentes.size > 0) return
    ronda++
    document.removeEventListener('visibilitychange', alVolverALaPestana)
    clearTimeout(espera)
    enCurso?.abort()
    enCurso = null
    fallos = 0
    vista = GEMINI_IDLE // al volver a montar no se enseña un "active" viejo
  }
}

function useGemini(): GeminiView {
  return useSyncExternalStore(
    suscribir,
    () => vista,
    () => GEMINI_IDLE
  )
}

export function GeminiBadge() {
  const { state, label } = useGemini()
  return (
    <div className={`gemini-badge is-${state}`} role="status" aria-live="polite">
      <span className="gemini-badge-dot" aria-hidden="true" />
      {label}
    </div>
  )
}

export function GeminiNote() {
  const { state, note, placeholder } = useGemini()
  return (
    <div className="glass-card gemini-note">
      <div className="gemini-note-head">
        <span className="caps">Strategy note (Gemini)</span>
        {state === 'degraded' && note && <span className="gemini-note-stale">Last known</span>}
      </div>
      <p className={note ? 'gemini-note-text' : 'gemini-note-text is-empty'}>
        {note ?? placeholder}
      </p>
    </div>
  )
}
