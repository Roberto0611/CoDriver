// Turno en vivo: Greedy y Nuez corren el mismo turno fresco en el backend y un
// juez les mete un cierre o un surge a media corrida. Mismo layout que el replay
// grabado (SimView): mapa, píldora arriba, panel a la izquierda, avisos abajo.
// El backend es dueño del reloj; aquí solo se pide el siguiente minuto y se pinta.

import { useEffect, useMemo, useRef, useState } from 'react'

import { cargarPuntos } from './lib/loader'
import {
  DEMO_SHOCKS,
  SPEEDS,
  endLive,
  getRehearsal,
  getZones,
  shockLive,
  startLive,
  tickLive,
  type DemoShockKind,
  type LiveRehearsal,
  type LiveSnapshot,
  type LiveStartParams,
  type LiveZone,
} from './lib/live'
import { applySnapshot, countersOf, initLiveState, type LiveState } from './lib/liveAccum'
import { zonasDePuntos } from './lib/liveEffect'
import { resaltarShock } from './map/shocks'
import { Counters } from './sim/Counters'
import { Decisions } from './sim/Decisions'
import { DecisionToasts } from './sim/DecisionToasts'
import { LiveControls, LiveStartForm, type LivePending, type LivePhase } from './sim/LiveControls'
import { ShockBanner } from './sim/ShockBanner'
import { useSimMap } from './sim/useSimMap'
import { Icon } from './ui/icons'
import { unlock } from './voice/nuez'
import './styles/live.css'

const MS_POR_TICK = 500 // 1 min simulado cada 0.5 s a ×1, igual que el replay

type Reintento = 'catalog' | 'start' | 'tick' | 'end'

const semillaNueva = () => 2000 + Math.floor(Math.random() * 98000)
const mensaje = (e: unknown) => (e instanceof Error ? e.message : String(e))

export default function LiveSimView() {
  const [phase, setPhase] = useState<LivePhase>('idle')
  const [live, setLive] = useState<LiveState | null>(null)
  const [speedIdx, setSpeedIdx] = useState(0)
  const [error, setError] = useState<{ message: string; retry: Reintento } | null>(null)
  const [pending, setPending] = useState<LivePending>(null)
  const [puntos, setPuntos] = useState<GeoJSON.FeatureCollection | null>(null)
  const [zones, setZones] = useState<LiveZone[]>([])
  const [rehearsal, setRehearsal] = useState<LiveRehearsal | null>(null)
  const [params, setParams] = useState<LiveStartParams>(() => ({
    seed: semillaNueva(),
    duracion_min: 120,
    hora_inicio: 14,
    vehiculo: 'moto',
    ancla: 4, // Tec
    margen_min: 10,
  }))

  // El loop lee refs, no estado: un setTimeout agendado hace tres renders no
  // debe decidir con la fase de entonces.
  const phaseRef = useRef<LivePhase>('idle')
  const speedRef = useRef(0)
  const sessionRef = useRef<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const tickEnVuelo = useRef(false)
  // Una sola fila de peticiones: un shock no se cruza con un tick y las respuestas
  // llegan en el orden en que el backend las corrió.
  const colaRef = useRef<Promise<unknown>>(Promise.resolve())
  const resaltados = useRef<{ endsAt: number; cleanup: () => void }[]>([])

  const cambiarFase = (f: LivePhase) => {
    phaseRef.current = f
    setPhase(f)
  }

  function enCola<T>(fn: () => Promise<T>): Promise<T> {
    const p = colaRef.current.then(fn)
    colaRef.current = p.catch(() => undefined)
    return p
  }

  const detenerTimer = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = null
  }

  const quitarResaltados = (hasta: number) => {
    resaltados.current = resaltados.current.filter((r) => {
      if (hasta < r.endsAt) return true
      r.cleanup()
      return false
    })
  }

  const aplicar = (snap: LiveSnapshot) =>
    setLive((prev) =>
      prev && prev.snapshot.session_id === snap.session_id ? applySnapshot(prev, snap) : prev
    )

  const fallar = (e: unknown, retry: Reintento) => {
    detenerTimer()
    cambiarFase('error')
    setError({ message: mensaje(e), retry })
  }

  // ── Catálogo: zonas, seed ensayado y puntos del mapa ──
  const cargarCatalogo = () => {
    cargarPuntos()
      .then(setPuntos)
      .catch(() =>
        setError({ message: "Couldn't load the map points (puntos.json)", retry: 'catalog' })
      )
    getZones()
      .then(setZones)
      .catch((e) => setError({ message: mensaje(e), retry: 'catalog' }))
    getRehearsal()
      .then(setRehearsal)
      .catch((e) => setError({ message: mensaje(e), retry: 'catalog' }))
  }

  useEffect(() => {
    cargarCatalogo()
    return () => {
      // Al salir de /live: nada de ticks ni respuestas tardías sobre un mapa muerto.
      detenerTimer()
      sessionRef.current = null
      quitarResaltados(Infinity)
    }
  }, [])

  // ── Loop de ticks: setTimeout encadenado, el siguiente solo cuando llegó el anterior ──
  const programar = (ms: number) => {
    detenerTimer()
    timerRef.current = setTimeout(() => void tick(), ms)
  }

  const tick = async () => {
    timerRef.current = null
    const sid = sessionRef.current
    if (!sid || phaseRef.current !== 'running' || tickEnVuelo.current) return
    tickEnVuelo.current = true
    try {
      const snap = await enCola(() => tickLive(sid))
      if (sessionRef.current !== sid) return
      aplicar(snap)
      if (snap.status !== 'running') void terminar(sid)
      else if (phaseRef.current === 'running') programar(MS_POR_TICK / SPEEDS[speedRef.current])
    } catch (e) {
      // Un tick perdido se lleva sus deltas: no se reintenta solo, se enseña.
      if (sessionRef.current === sid) fallar(e, 'tick')
    } finally {
      tickEnVuelo.current = false
    }
  }

  const reanudar = () => {
    setError(null)
    cambiarFase('running')
    if (!tickEnVuelo.current) programar(0)
  }

  // ── Acciones ──
  const iniciar = async () => {
    unlock() // en el click: después el navegador ya deja sonar la voz
    detenerTimer()
    sessionRef.current = null
    quitarResaltados(Infinity)
    setError(null)
    cambiarFase('starting')
    try {
      const snap = await enCola(() => startLive(params))
      sessionRef.current = snap.session_id
      setLive(initLiveState(snap, { vehiculo: params.vehiculo, margen_min: params.margen_min }))
      reanudar()
    } catch (e) {
      fallar(e, 'start')
    }
  }

  const terminar = async (sid: string) => {
    detenerTimer()
    if (phaseRef.current === 'running') cambiarFase('paused')
    setPending('end')
    try {
      const snap = await enCola(() => endLive(sid))
      if (sessionRef.current !== sid) return
      aplicar(snap)
      setError(null)
      cambiarFase('finished')
    } catch (e) {
      if (sessionRef.current === sid) fallar(e, 'end')
    } finally {
      setPending(null)
    }
  }

  const disparar = async (kind: DemoShockKind) => {
    const sid = sessionRef.current
    if (!sid) return
    setPending(kind)
    try {
      const { shock, snapshot } = await enCola(() => shockLive(sid, DEMO_SHOCKS[kind]))
      if (sessionRef.current !== sid) return
      aplicar(snapshot)
      // El resaltado es solo visual y va después de que el backend confirmó.
      const zona = zones.find((z) => z.id === shock.zone)
      const cleanup = resaltarShock(mapRef.current, {
        type: shock.type,
        zoneCenter: zona ? [zona.lon, zona.lat] : undefined,
        road: shock.road ?? undefined,
      })
      resaltados.current.push({ endsAt: shock.ends_at_min, cleanup })
    } catch (e) {
      if (sessionRef.current === sid) fallar(e, 'tick')
    } finally {
      setPending(null)
    }
  }

  const reintentar = () => {
    if (!error) return
    const sid = sessionRef.current
    if (error.retry === 'catalog') {
      setError(null)
      cargarCatalogo()
    } else if (error.retry === 'start' || !sid) void iniciar()
    else if (error.retry === 'end') void terminar(sid)
    else reanudar()
  }

  // Vuelve al formulario. La sesión vieja se suelta (sus respuestas tardías se
  // ignoran) pero su banner y contadores se quedan hasta que arranque otra.
  const nuevoTurno = () => {
    detenerTimer()
    sessionRef.current = null
    setError(null)
    cambiarFase('idle')
  }

  const playPause = () => {
    if (phase === 'idle') void iniciar()
    else if (phase === 'running') {
      detenerTimer()
      cambiarFase('paused')
    } else if (phase === 'paused') reanudar()
    else if (phase === 'error') reintentar()
  }

  const cambiarVelocidad = (i: number) => {
    speedRef.current = i
    setSpeedIdx(i)
  }

  // ── Derivados ──
  const snap = live?.snapshot
  const ultimoFrame = live?.nuez.frames.at(-1)
  // Tras /live/end el minuto salta al final sin frames: el mapa se queda en el último pintado.
  const t = snap ? Math.max(0, Math.min(snap.minute - 1, ultimoFrame?.t ?? 0)) : 0
  const minute = snap?.minute ?? 0
  const zonaDe = useMemo(() => (puntos ? zonasDePuntos(puntos) : []), [puntos])

  const { mapContainer, mapRef } = useSimMap({
    t,
    greedy: live?.greedy ?? null,
    nuez: live?.nuez ?? null,
    puntos,
  })

  // Cada resaltado se quita cuando el shock expira en el reloj del backend.
  useEffect(() => {
    quitarResaltados(minute)
  }, [minute])

  const enForma =
    phase === 'idle' || phase === 'starting' || (phase === 'error' && error?.retry === 'start')
  const terminado = phase === 'finished' || snap?.status === 'ended'

  return (
    <div className="app">
      <div ref={mapContainer} className="map-container" />

      <div className={`loading-overlay ${phase === 'starting' ? 'active' : ''}`}>
        <div className="loading-spinner" />
        <div className="loading-text">Starting live shift…</div>
      </div>

      <div className="logo live-logo" role="img" aria-label="Nuez">
        {Icon.mark}
      </div>

      <DecisionToasts frame={ultimoFrame} seed={snap?.seed ?? null} t={ultimoFrame?.t ?? 0} />

      <LiveControls
        phase={phase}
        hasSession={live !== null && !terminado}
        startHour={enForma ? params.hora_inicio : (snap?.start_hour ?? params.hora_inicio)}
        minute={enForma ? 0 : minute}
        duration={enForma ? params.duracion_min : (snap?.duration_min ?? params.duracion_min)}
        speedIdx={speedIdx}
        pending={pending}
        onPlayPause={playPause}
        onSpeed={cambiarVelocidad}
        onShock={(k) => void disparar(k)}
        onEnd={() => sessionRef.current && void terminar(sessionRef.current)}
        onNewShift={nuevoTurno}
      />

      <div className="overlay-panel">
        {error && (
          <div className="glass-card live-error" role="alert">
            <span className="caps">Live backend error</span>
            <p className="live-error-text">{error.message}</p>
            <div className="live-error-actions">
              <button className="btn-primary" onClick={reintentar}>
                Retry
              </button>
              {(error.retry === 'tick' || error.retry === 'end') && (
                <button className="live-btn" onClick={nuevoTurno}>
                  Start new shift
                </button>
              )}
            </div>
          </div>
        )}

        {live && <ShockBanner live={live} zonaDe={zonaDe} />}

        {enForma && (
          <LiveStartForm
            params={params}
            zones={zones}
            rehearsal={rehearsal}
            disabled={phase === 'starting'}
            onChange={setParams}
            onNewSeed={() => setParams((p) => ({ ...p, seed: semillaNueva() }))}
            onStart={() => void iniciar()}
          />
        )}

        {live && snap && (
          <div className="glass-card">
            <Counters
              greedy={countersOf(snap.greedy)}
              nuez={countersOf(snap.nuez)}
              greedyMeta={live.greedy.meta}
              nuezMeta={live.nuez.meta}
              terminado={terminado}
            />
            {snap.event_log && (
              <div className="live-event-log">
                <span className="caps">Event log</span>
                <span className="live-event-log-path">{snap.event_log}</span>
              </div>
            )}
          </div>
        )}

        {live && snap && (
          <div className="glass-card">
            <Decisions frames={live.nuez.frames} t={t} horaInicio={snap.start_hour} />
          </div>
        )}
      </div>
    </div>
  )
}
