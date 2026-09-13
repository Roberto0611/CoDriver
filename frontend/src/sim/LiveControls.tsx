// Controles del turno en vivo. LiveControls va en la píldora de arriba, donde el
// replay tiene su play y su velocidad; LiveStartForm va en el panel izquierdo,
// donde el replay tiene su selector de seed. Nada se mueve respecto a /sim.

import { useEffect, useState } from 'react'
import type { Vehiculo } from '../contract'
import {
  DEMO_SHOCKS,
  SPEEDS,
  type DemoShockKind,
  type LiveRehearsal,
  type LiveStartParams,
  type LiveZone,
} from '../lib/live'
import { minutosAHora } from '../lib/sim'
import type { GeminiView } from '../lib/gemini-status'
import { Icon } from '../ui/icons'
import { getVoiceLanguage, setVoiceLanguage, onVoiceLanguage, type FuenteVoz } from '../voice/nuez'
import { GeminiBadgeView } from './GeminiStatus'
import { ModeSwitch } from './ModeSwitch'

export type LivePhase = 'idle' | 'starting' | 'running' | 'paused' | 'finished' | 'error'
export type LivePending = DemoShockKind | 'end' | null

const VEHICULOS: { value: Vehiculo; label: string }[] = [
  { value: 'moto', label: 'Motorcycle' },
  { value: 'car', label: 'Car' },
  { value: 'bike', label: 'Bike' },
]
// 510 = la jornada de 8.5 h del practice pack; /live/start la acepta hasta MAX_TURNO_MIN.
const DURACIONES = [120, 480, 510] as const
const RETRASO_NOMBRE = `Restaurant +${DEMO_SHOCKS.delay.slip_min} min`
const RETRASO_TITULO = `${RETRASO_NOMBRE}: the next order to be offered is ready ${DEMO_SHOCKS.delay.slip_min} min late`

// ── Píldora ──────────────────────────────────────────────────────────────

interface ControlsProps {
  gemini: GeminiView
  phase: LivePhase
  hasSession: boolean
  startHour: number
  minute: number
  duration: number
  speedIdx: number
  voice: boolean
  voiceSource: FuenteVoz
  pending: LivePending
  onPlayPause: () => void
  onSpeed: (idx: number) => void
  onVoice: () => void
  onShock: (kind: DemoShockKind) => void
  onEnd: () => void
  onNewShift: () => void
}

export function LiveControls(p: ControlsProps) {
  const vivo = p.phase === 'running' || p.phase === 'paused'
  const ocupado = p.pending !== null
  const shockListo = vivo && !ocupado
  
  const [lang, setLang] = useState(() => getVoiceLanguage().elLang)
  useEffect(() => {
    return onVoiceLanguage(() => setLang(getVoiceLanguage().elLang))
  }, [])
  
  const vozTitulo = !p.voice
    ? 'Navie voice off'
    : p.voiceSource === 'browser'
      ? 'Navie voice on (ElevenLabs unavailable, using browser voice)'
      : 'Navie voice on (ElevenLabs)'

  const play = {
    idle: { title: 'Start live shift', icon: Icon.play, disabled: false },
    starting: { title: 'Starting…', icon: Icon.play, disabled: true },
    running: { title: 'Pause', icon: Icon.pause, disabled: false },
    paused: { title: 'Resume', icon: Icon.play, disabled: ocupado },
    finished: { title: 'Shift over', icon: Icon.play, disabled: true },
    error: { title: 'Retry', icon: Icon.play, disabled: ocupado },
  }[p.phase]

  return (
    <div className="timeline-panel">
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', paddingRight: '12px', borderRight: '1px solid var(--hairline)' }}>
        <GeminiBadgeView view={p.gemini} />
      </div>

      <div className="timeline-controls">
        <button
          className="timeline-btn-play"
          title={play.title}
          aria-label={play.title}
          disabled={play.disabled}
          onClick={p.onPlayPause}
        >
          {play.icon}
        </button>
      </div>

      <div className="timeline-scrubber">
        <div className="timeline-time-display num">{minutosAHora(p.startHour, p.minute)}</div>
        <div className="timeline-slider-track">
          <progress
            className="live-progress"
            value={p.minute}
            max={p.duration}
            aria-label="Shift progress"
          />
          <div className="timeline-labels">
            <span>{minutosAHora(p.startHour, 0)}</span>
            <span>{minutosAHora(p.startHour, p.duration)}</span>
          </div>
        </div>
      </div>

      <div className="speed-selector">
        {SPEEDS.map((s, i) => (
          <button
            key={s}
            className={`speed-btn ${p.speedIdx === i ? 'is-active' : ''}`}
            onClick={() => p.onSpeed(i)}
          >
            {s}x
          </button>
        ))}
        {/* El mismo botón de voz que /sim (VozToggle), sin su lógica de replay. Solo icono:
            con el texto la píldora se mete bajo el logo a 1280. */}
        <div className="voz-container">
          <button
            className={`speed-btn voz-toggle ${p.voice ? 'is-active' : ''}`}
            title={vozTitulo}
            aria-label={vozTitulo}
            aria-pressed={p.voice}
            onClick={p.onVoice}
          >
            {p.voice ? Icon.voice : Icon.voiceOff}
          </button>
          <div className="voz-lang-menu">
            <button className="voz-menu-item" onClick={() => setVoiceLanguage('es', 'es-MX')}>
              <img src="https://flagcdn.com/mx.svg" width="20" alt="MX" /> Español {lang === 'es' && '✓'}
            </button>
            <button className="voz-menu-item" onClick={() => setVoiceLanguage('en', 'en-US')}>
              <img src="https://flagcdn.com/us.svg" width="20" alt="US" /> English {lang === 'en' && '✓'}
            </button>
            <button className="voz-menu-item" onClick={() => setVoiceLanguage('hi', 'hi-IN')}>
              <img src="https://flagcdn.com/in.svg" width="20" alt="IN" /> Hindi {lang === 'hi' && '✓'}
            </button>
          </div>
        </div>
      </div>

      <div className="live-actions">
        {/* Los tres shocks vivían como botones sueltos y no cabían a 1280x800;
            ahora son un solo dropdown por hover, como un menú de vidrio de menú. */}
        <div className="live-events">
          <button className="live-btn" disabled={!shockListo}>
            {Icon.clock}
            Events
            {Icon.chevron}
          </button>
          <div className="live-events-menu">
            <button
              className="live-events-item is-closure"
              disabled={!shockListo}
              onClick={() => p.onShock('closure')}
            >
              {Icon.closure}
              {p.pending === 'closure' ? 'Closing…' : 'Close Constitución'}
            </button>
            <button
              className="live-events-item is-surge"
              disabled={!shockListo}
              onClick={() => p.onShock('surge')}
            >
              {Icon.speed}
              {p.pending === 'surge' ? 'Triggering…' : 'Trigger surge'}
            </button>
            <button
              className="live-events-item is-delay"
              disabled={!shockListo}
              title={p.pending === 'delay' ? 'Delaying…' : RETRASO_TITULO}
              onClick={() => p.onShock('delay')}
            >
              {Icon.clock}
              {p.pending === 'delay' ? 'Delaying…' : RETRASO_NOMBRE}
            </button>
          </div>
        </div>
        {p.phase === 'finished' ? (
          <button className="live-btn" onClick={p.onNewShift}>
            Start new shift
          </button>
        ) : (
          <button
            className="live-btn"
            disabled={!p.hasSession || ocupado || p.phase === 'starting'}
            onClick={p.onEnd}
          >
            {p.pending === 'end' ? 'Ending…' : 'End shift'}
          </button>
        )}
      </div>

      <ModeSwitch />
    </div>
  )
}

// ── Formulario de inicio (panel izquierdo) ───────────────────────────────

interface FormProps {
  params: LiveStartParams
  zones: LiveZone[]
  rehearsal: LiveRehearsal | null
  disabled: boolean
  onChange: (params: LiveStartParams) => void
  onNewSeed: () => void
  onStart: () => void
}

export function LiveStartForm({
  params,
  zones,
  rehearsal,
  disabled,
  onChange,
  onNewSeed,
  onStart,
}: FormProps) {
  const set = (cambio: Partial<LiveStartParams>) => onChange({ ...params, ...cambio })
  const seedValido = Number.isInteger(params.seed) && params.seed >= 0
  const ensayado = rehearsal !== null && params.seed === rehearsal.seed
  // Sin catálogo (backend caído) queda Tec, la zona por defecto del backend.
  const anclas = zones.length ? zones : [{ id: 4, name: 'Tec', lat: 0, lon: 0 }]

  return (
    <div className="glass-card live-form">
      <div className="field">
        <label htmlFor="live-seed">Seed</label>
        <div className="live-seed-row">
          <input
            id="live-seed"
            className="live-input num"
            type="number"
            min={0}
            step={1}
            value={Number.isNaN(params.seed) ? '' : params.seed}
            onChange={(e) => set({ seed: e.target.valueAsNumber })}
          />
          <button className="seed-btn" type="button" onClick={onNewSeed}>
            New seed
          </button>
          <button
            className={`seed-btn ${ensayado ? 'is-active' : ''}`}
            type="button"
            disabled={!rehearsal}
            onClick={() => rehearsal && set({ seed: rehearsal.seed })}
          >
            Rehearsed
          </button>
        </div>
        {ensayado && (
          <span className="live-hint">
            Rehearsed run: close Constitución at{' '}
            <span className="num">
              {minutosAHora(params.hora_inicio, rehearsal.closure_minute)}
            </span>
            , then Restaurant +{rehearsal.delay_slip_min} min at{' '}
            <span className="num">{minutosAHora(params.hora_inicio, rehearsal.delay_minute)}</span>.
          </span>
        )}
      </div>

      <div className="live-form-row">
        <div className="field">
          <label htmlFor="live-vehicle">Vehicle</label>
          <div className="select">
            <select
              id="live-vehicle"
              value={params.vehiculo}
              onChange={(e) => set({ vehiculo: e.target.value as Vehiculo })}
            >
              {VEHICULOS.map((v) => (
                <option key={v.value} value={v.value}>
                  {v.label}
                </option>
              ))}
            </select>
            {Icon.chevron}
          </div>
        </div>
        <div className="field">
          <label htmlFor="live-duration">Shift</label>
          <div className="select">
            <select
              id="live-duration"
              value={params.duracion_min}
              onChange={(e) => set({ duracion_min: Number(e.target.value) })}
            >
              {DURACIONES.map((d) => (
                <option key={d} value={d}>
                  {d / 60} h
                </option>
              ))}
            </select>
            {Icon.chevron}
          </div>
        </div>
      </div>

      <div className="field">
        <label htmlFor="live-anchor">Home zone</label>
        <div className="select">
          <select
            id="live-anchor"
            value={params.ancla}
            onChange={(e) => set({ ancla: Number(e.target.value) })}
          >
            {anclas.map((z) => (
              <option key={z.id} value={z.id}>
                {z.name}
              </option>
            ))}
          </select>
          {Icon.chevron}
        </div>
      </div>

      <button className="btn-primary" disabled={disabled || !seedValido} onClick={onStart}>
        {Icon.play}
        {disabled ? 'Starting…' : 'Start live shift'}
      </button>
    </div>
  )
}
