// Banner del shock en vivo: qué se inyectó, hasta cuándo dura, qué le cambió a la
// ruta de cada agente y cómo reaccionó cada uno en su primera decisión después.
// Es el momento que se narra en el pitch, así que no se oculta solo: se queda
// hasta que arranca otra sesión.

import type { Decision } from '../contract'
import { esSeguridad, etiquetaRestriccion, textoDecisionCorto } from '../lib/decision-text'
import type { AgentKey } from '../lib/live'
import { firstDecisionFrom, type LiveShockSeen, type LiveState } from '../lib/liveAccum'
import { efectoShock, type AgentShockEffect } from '../lib/liveEffect'
import { minutosAHora } from '../lib/sim'
import { Icon } from '../ui/icons'

interface Props {
  live: LiveState
  /** Zona de cada punto del mapa; vacío mientras no carga puntos.json. */
  zonaDe: readonly string[]
}

const AGENTES = ['greedy', 'nuez'] as const

function titulo(s: LiveShockSeen): string {
  if (s.type === 'closure') return 'Road closure'
  if (s.type === 'surge') return `Surge ×${s.multiplier.toFixed(1)}`
  return 'Rain'
}

function lugar(s: LiveShockSeen): string {
  if (s.road && s.zone_name) return `${s.road}, ${s.zone_name}`
  return s.road ?? s.zone_name ?? 'Whole city'
}

function vigencia(s: LiveShockSeen, minute: number, startHour: number): string {
  const hora = minutosAHora(startHour, s.ends_at_min)
  return minute >= s.ends_at_min ? `ended at ${hora}` : `active until ${hora}`
}

// Greedy no calcula ventaja: sin esto su línea diría "(+? edge)".
function lineaDecision(agente: AgentKey, d: Decision): string {
  if (agente === 'greedy' && d.accion === 'aceptar') {
    const t = d.terminos
    return `Accept: MXN ${t.pago_neto?.toFixed(0) ?? '?'} for ${t.minutos?.toFixed(0) ?? '?'} min`
  }
  return textoDecisionCorto(d)
}

const plural = (n: number, una: string, varias: string) => `${n} ${n === 1 ? una : varias}`

function lineaRuta(e: AgentShockEffect): string | null {
  const r = e.route
  if (!r) return null
  if (r.kind === 'closure') {
    if (r.legs === 0) return `No legs through ${r.zone} yet`
    return `${plural(r.legs, 'leg', 'legs')} through ${r.zone}, ${r.minutes.toFixed(0)} min`
  }
  if (r.offers === 0) return `No offers from ${r.zone} yet`
  return `${plural(r.offers, 'offer', 'offers')} from ${r.zone}, took ${r.accepted}`
}

function Efecto({
  agente,
  decision,
  efecto,
  startHour,
}: {
  agente: AgentKey
  decision: Decision | null
  efecto: AgentShockEffect
  startHour: number
}) {
  const acepta = decision?.accion === 'aceptar'
  const ruta = lineaRuta(efecto)
  return (
    <div className="shock-effect-row">
      <div className="shock-effect-head">
        <span className={`counter-agent-label is-${agente}`}>
          {agente === 'nuez' ? 'Nuez' : 'Greedy'}
        </span>
        {decision && (
          <span className="decision-time num">{minutosAHora(startHour, decision.t)}</span>
        )}
      </div>

      {ruta && <span className="shock-effect-route num">{ruta}</span>}
      {efecto.cancelled > 0 && (
        <span className="shock-effect-route num">
          {plural(efecto.cancelled, 'order', 'orders')} cancelled since
        </span>
      )}

      {decision ? (
        <>
          <span className={`shock-decision ${acepta ? 'is-accept' : 'is-skip'}`}>
            {acepta ? Icon.accept : Icon.skip}
            {lineaDecision(agente, decision)}
          </span>
          {agente === 'nuez' && decision.razon && (
            <p className="shock-effect-reason">{decision.razon}</p>
          )}
          {agente === 'nuez' && decision.restriccion && (
            <span
              className={`decision-chip ${esSeguridad(decision.restriccion) ? 'is-safety' : 'is-money'}`}
            >
              {esSeguridad(decision.restriccion) ? Icon.shield : Icon.dollar}
              {etiquetaRestriccion(decision.restriccion)}
            </span>
          )}
        </>
      ) : (
        <span className="shock-effect-waiting">Waiting for the next offer…</span>
      )}
    </div>
  )
}

export function ShockBanner({ live, zonaDe }: Props) {
  const { shocks, snapshot } = live
  if (shocks.length === 0) return null
  const actual = shocks[shocks.length - 1]
  const anteriores = shocks.slice(0, -1).reverse()
  const efectos = efectoShock(live, actual, zonaDe)
  const { minute, start_hour: startHour } = snapshot

  return (
    <section className="glass-card shock-banner" aria-live="polite">
      <div className="shock-banner-head">
        <span className={`shock-banner-icon is-${actual.type}`}>
          {actual.type === 'surge' ? Icon.speed : Icon.closure}
        </span>
        <div className="shock-banner-heading">
          <span className="caps">{titulo(actual)}</span>
          <strong className="shock-banner-title">{lugar(actual)}</strong>
        </div>
      </div>

      <span className="shock-banner-status num">
        Injected at {minutosAHora(startHour, actual.starts_at_min)},{' '}
        {vigencia(actual, minute, startHour)}
      </span>

      <div className="shock-effect">
        {AGENTES.map((a) => (
          <Efecto
            key={a}
            agente={a}
            decision={firstDecisionFrom(live[a].frames, actual.starts_at_min)}
            efecto={efectos[a]}
            startHour={startHour}
          />
        ))}
      </div>

      {anteriores.length > 0 && (
        <ul className="shock-banner-earlier">
          {anteriores.map((s) => (
            <li key={`${s.type}-${s.starts_at_min}-${s.zone}`} className="num">
              {titulo(s)} · {lugar(s)} · {vigencia(s, minute, startHour)}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
