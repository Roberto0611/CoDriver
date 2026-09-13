// Banner del shock en vivo: qué se inyectó, hasta cuándo dura, qué le cambió a la
// ruta de cada agente y cómo reaccionó cada uno: su primera decisión después, o en un
// delay su decisión sobre el pedido atrasado (lib/liveEffect.reaccionAlShock).
// Es el momento que se narra en el pitch, así que no se oculta solo: se queda
// hasta que arranca otra sesión. El texto sale de lib/shockCopy (probado).

import type { Decision } from '../contract'
import { textoDecisionCorto } from '../lib/decision-text'
import type { AgentKey } from '../lib/live'
import type { LiveState } from '../lib/liveAccum'
import { efectoShock, reaccionAlShock } from '../lib/liveEffect'
import { shockCopy, shockLine, type ShockCopy, type ShockCopyContext } from '../lib/shockCopy'
import { minutosAHora } from '../lib/sim'
import { Icon } from '../ui/icons'
import { RestriccionChip } from './Decisions'

interface Props {
  live: LiveState
  /** Zona de cada punto del mapa; vacío mientras no carga puntos.json. */
  zonaDe: readonly string[]
}

const AGENTES = ['greedy', 'nuez'] as const

const ICONO = { surge: Icon.speed, delay: Icon.clock, closure: Icon.closure, rain: Icon.closure }

// Greedy no calcula ventaja: sin esto su línea diría "(+? edge)".
function lineaDecision(agente: AgentKey, d: Decision): string {
  if (agente === 'greedy' && d.accion === 'aceptar') {
    const t = d.terminos
    return `Accept: MXN ${t.pago_neto?.toFixed(0) ?? '?'} for ${t.minutos?.toFixed(0) ?? '?'} min`
  }
  return textoDecisionCorto(d)
}

function Efecto({
  agente,
  decision,
  copy,
  startHour,
}: {
  agente: AgentKey
  decision: Decision | null
  copy: ShockCopy
  startHour: number
}) {
  const acepta = decision?.accion === 'aceptar'
  return (
    <div className="shock-effect-row">
      <div className="shock-effect-head">
        <span className={`counter-agent-label is-${agente}`}>
          {agente === 'nuez' ? 'Navie' : 'Greedy'}
        </span>
        {decision && (
          <span className="decision-time num">{minutosAHora(startHour, decision.t)}</span>
        )}
      </div>

      {copy.route[agente] && <span className="shock-effect-route num">{copy.route[agente]}</span>}
      {copy.cancelled[agente] && (
        <span className="shock-effect-route num">{copy.cancelled[agente]}</span>
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
            <RestriccionChip restriccion={decision.restriccion} />
          )}
        </>
      ) : (
        <span className="shock-effect-waiting">{copy.noDecision}</span>
      )}
    </div>
  )
}

export function ShockBanner({ live, zonaDe }: Props) {
  const { shocks, snapshot } = live
  if (shocks.length === 0) return null
  const actual = shocks[shocks.length - 1]
  const anteriores = shocks.slice(0, -1).reverse()
  const ctx: ShockCopyContext = {
    minute: snapshot.minute,
    durationMin: snapshot.duration_min,
    startHour: snapshot.start_hour,
    status: snapshot.status,
    lastFrameT: live.nuez.frames.at(-1)?.t ?? -1,
  }
  const copy = shockCopy(actual, efectoShock(live, actual, zonaDe), ctx)

  return (
    <section className="glass-card shock-banner" aria-live="polite">
      <div className="shock-banner-head">
        <span className={`shock-banner-icon is-${actual.type}`}>{ICONO[actual.type]}</span>
        <div className="shock-banner-heading">
          <span className="caps">{copy.title}</span>
          <strong className="shock-banner-title">{copy.place}</strong>
        </div>
      </div>

      <span className="shock-banner-status num">{copy.status}</span>
      {copy.coverage && <span className="shock-banner-status num">{copy.coverage}</span>}

      <div className="shock-effect">
        {AGENTES.map((a) => (
          <Efecto
            key={a}
            agente={a}
            decision={reaccionAlShock(live[a].frames, actual)}
            copy={copy}
            startHour={ctx.startHour}
          />
        ))}
      </div>

      {anteriores.length > 0 && (
        <ul className="shock-banner-earlier">
          {anteriores.map((s) => (
            <li key={`${s.type}-${s.starts_at_min}-${s.zone}-${s.order_id}`} className="num">
              {shockLine(s, ctx)}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
