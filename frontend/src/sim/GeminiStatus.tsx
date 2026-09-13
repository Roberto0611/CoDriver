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
import { NavieCompass } from '../navie/NavieCompass'
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

export function useGemini(): GeminiView {
  return useSyncExternalStore(
    suscribir,
    () => vista,
    () => GEMINI_IDLE
  )
}

export function GeminiBadge() {
  return <GeminiBadgeView view={useGemini()} />
}

/** Presentación reutilizable: /live entrega su propio estado de Gemini en cada snapshot. */
export function GeminiBadgeView({ view }: { view: GeminiView }) {
  const { state, label } = view
  const mode = state === 'active' ? 'wink' : 'searching'

  return (
    <div
      className={`speed-btn gemini-badge is-${state} ${state === 'active' ? 'is-active' : ''}`}
      role="status"
      aria-live="polite"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        height: '32px',
        padding: '0 12px 0 6px',
        cursor: 'default',
        userSelect: 'none',
      }}
    >
      <div
        style={{
          width: '24px',
          height: '24px',
          borderRadius: '50%',
          background: 'var(--plum)',
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        <div style={{ transform: 'scale(0.15)', transformOrigin: 'center center', position: 'absolute' }}>
          <NavieCompass mode={mode} />
        </div>
      </div>
      <span className="gemini-badge-dot" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function GeminiNote() {
  return <GeminiNoteView view={useGemini()} />
}

/** La misma nota del replay, alimentada por el turno que el juez está viendo en vivo. */
export function GeminiNoteView({ view }: { view: GeminiView }) {
  const { state, note, placeholder } = view
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
