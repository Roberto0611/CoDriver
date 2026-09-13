// Reproductor de turnos grabados: dos motos (Greedy vs Nuez) corren el
// mismo turno lado a lado, con contadores de ganancias y panel de decisiones.
// Los datos vienen de frontend/public/ (JSON grabados).

import { useEffect, useState } from 'react'


import { Icon } from './ui/icons'
import { NavieCompass } from './navie/NavieCompass'
import { cargarTurnosPorSeed, cargarIndiceTurnos, cargarPuntos } from './lib/loader'
import { minutosAHora, contadoresEnT } from './lib/sim'
import type { TurnoData, TurnoIndex } from './lib/turno'
import { Counterfactual } from './sim/Counterfactual'
import { Counters } from './sim/Counters'
import { Decisions } from './sim/Decisions'
import { Distribution } from './sim/Distribution'
import { DecisionToasts } from './sim/DecisionToasts'
import { DecisionHistory } from './sim/DecisionHistory'
import { GeminiBadge, GeminiNote } from './sim/GeminiStatus'
import { ModeSwitch } from './sim/ModeSwitch'
import { useSimMap } from './sim/useSimMap'
import { VozToggle } from './voice/VozToggle'

const SPEEDS = [1, 2, 4] as const
const MS_PER_STEP_BASE = 500 // 1 min simulado cada 0.5s a velocidad ×1

export default function SimView() {
  const [loading, setLoading] = useState(true)
  const [indice, setIndice] = useState<TurnoIndex | null>(null)
  const [seed, setSeed] = useState<number | null>(null)
  const [greedy, setGreedy] = useState<TurnoData | null>(null)
  const [nuez, setNuez] = useState<TurnoData | null>(null)
  const [puntos, setPuntos] = useState<GeoJSON.FeatureCollection | null>(null)
  const [t, setT] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [speedIdx, setSpeedIdx] = useState(0)
  const [maxT, setMaxT] = useState(120)

  // Cargar índice y puntos al montar
  useEffect(() => {
    Promise.all([cargarIndiceTurnos(), cargarPuntos()]).then(([idx, pts]) => {
      setIndice(idx)
      setPuntos(pts)
      // Seleccionar el primer seed disponible
      if (idx.turnos.length > 0) {
        setSeed(idx.turnos[0].seed)
      }
    })
  }, [])

  // Cargar turno cuando cambia el seed
  useEffect(() => {
    if (seed == null) return
    setLoading(true)
    setIsPlaying(false)
    setT(0)
    cargarTurnosPorSeed(seed).then(({ greedy: g, nuez: n }) => {
      setGreedy(g)
      setNuez(n)
      setMaxT(g.config.duracion_min)
      setLoading(false)
    })
  }, [seed])

  // Mapa, motos, estelas y llegadas al minuto `t`
  const { mapContainer } = useSimMap({ t, greedy, nuez, puntos })

  // Auto-play
  useEffect(() => {
    if (!isPlaying) return

    const ms = MS_PER_STEP_BASE / SPEEDS[speedIdx]
    const interval = setInterval(() => {
      setT((prev) => {
        if (prev >= maxT - 1) {
          setIsPlaying(false)
          return maxT - 1
        }
        return prev + 1
      })
    }, ms)

    return () => clearInterval(interval)
  }, [isPlaying, speedIdx, maxT])

  // Helpers
  const horaInicio = greedy?.config.hora_inicio ?? 14

  const stepMinute = (delta: number) => {
    setT((prev) => Math.max(0, Math.min(maxT - 1, prev + delta)))
  }

  const handleTogglePlay = () => {
    if (t >= maxT - 1) setT(0)
    setIsPlaying((prev) => !prev)
  }

  const greedyCounters = greedy
    ? contadoresEnT(greedy.frames, t)
    : { ganado: 0, entregas: 0, saltadas: 0 }
  const nuezCounters = nuez
    ? contadoresEnT(nuez.frames, t)
    : { ganado: 0, entregas: 0, saltadas: 0 }
  const terminado = t >= maxT - 1

  let lastDecisionId = undefined
  if (nuez && nuez.frames) {
    for (let i = Math.min(t, nuez.frames.length - 1); i >= 0; i--) {
      if (nuez.frames[i].decisiones.length > 0) {
        lastDecisionId = `${i}-${nuez.frames[i].decisiones[nuez.frames[i].decisiones.length - 1].oferta_id}`
        break
      }
    }
  }

  return (
    <div className="app">
      {/* Mapa */}
      <div ref={mapContainer} className="map-container" />

      {/* Loading */}
      <div className={`loading-overlay ${loading ? 'active' : ''}`}>
        <div className="loading-spinner" />
        <div className="loading-text">Loading shift…</div>
      </div>

      {/* Avisos de decisión: aceptado arriba, bloqueado por seguridad abajo */}
      <DecisionToasts frame={nuez?.frames[t]} seed={seed} t={t} />

      {/* Timeline */}
      <div className="timeline-panel">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', paddingRight: '12px', borderRight: '1px solid var(--hairline)' }}>
          <GeminiBadge />
          <div style={{ width: '38px', height: '38px', borderRadius: '50%', background: 'var(--plum)', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
            <div style={{ transform: 'scale(0.22)', transformOrigin: 'center center', position: 'absolute' }}>
              <NavieCompass mode="idle" />
            </div>
          </div>
        </div>

        <div className="timeline-controls">
          <button className="timeline-btn-round" title="Back 1 min" onClick={() => stepMinute(-1)}>
            {Icon.stepBack}
          </button>

          <button
            className="timeline-btn-play"
            title={isPlaying ? 'Pause' : 'Play'}
            onClick={handleTogglePlay}
          >
            {isPlaying ? Icon.pause : Icon.play}
          </button>

          <button
            className="timeline-btn-round"
            title="Forward 1 min"
            onClick={() => stepMinute(1)}
          >
            {Icon.stepForward}
          </button>
        </div>

        <div className="timeline-scrubber">
          <div className="timeline-time-display num">{minutosAHora(horaInicio, t)}</div>

          <div className="timeline-slider-track">
            <input
              type="range"
              min={0}
              max={maxT - 1}
              step={1}
              value={t}
              onChange={(e) => setT(Number(e.target.value))}
              className="timeline-slider"
            />
            <div className="timeline-labels">
              <span>{minutosAHora(horaInicio, 0)}</span>
              <span>{minutosAHora(horaInicio, maxT)}</span>
            </div>
          </div>
        </div>

        {/* Velocidad */}
        <div className="speed-selector">
          {SPEEDS.map((s, i) => (
            <button
              key={s}
              className={`speed-btn ${speedIdx === i ? 'is-active' : ''}`}
              onClick={() => setSpeedIdx(i)}
            >
              {s}x
            </button>
          ))}
          {nuez && (
            <VozToggle
              frames={nuez.frames}
              t={t}
              isPlaying={isPlaying}
              vehiculo={nuez.config.vehiculo}
            />
          )}
        </div>

        {/* Replay grabado / live */}
        <ModeSwitch />
      </div>

      {/* Panel izquierdo */}
      <div className="overlay-panel">
        {/* Nota de Gemini */}
        <GeminiNote />

        {/* Selector de seed */}
        {indice && (
          <div className="glass-card">
            <div className="seed-selector">
              <span className="seed-selector-title">Recorded Shifts</span>
              <div className="seed-list">
                {indice.turnos.map((entry) => (
                  <button
                    key={entry.seed}
                    className={`seed-btn ${seed === entry.seed ? 'is-active' : ''}`}
                    onClick={() => setSeed(entry.seed)}
                  >
                    Seed {entry.seed}
                    <span
                      className={`seed-delta ${entry.delta_pct >= 0 ? 'is-positive' : 'is-negative'}`}
                    >
                      {entry.delta_pct >= 0 ? '+' : ''}
                      {entry.delta_pct.toFixed(0)}%
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Distribución */}
        {indice && <Distribution />}

        {/* Contadores */}
        {greedy && nuez && (
          <div className="glass-card">
            <Counters
              greedy={greedyCounters}
              nuez={nuezCounters}
              greedyMeta={greedy.meta}
              nuezMeta={nuez.meta}
              terminado={terminado}
            />
            <Counterfactual seed={seed} terminado={terminado} horaInicio={horaInicio} />
          </div>
        )}

        {/* Decisiones y Analytics */}
        {nuez && (
          <div
            className="glass-card"
            style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}
          >
            <DecisionHistory lastDecisionId={lastDecisionId} />
            <div style={{ borderTop: '1px solid var(--surface-high)' }} />
            <Decisions frames={nuez.frames} t={t} horaInicio={horaInicio} />
          </div>
        )}
      </div>
    </div>
  )
}
