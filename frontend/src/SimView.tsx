// Reproductor de turnos grabados: dos motos (Greedy vs Nuez) corren el
// mismo turno lado a lado, con contadores de ganancias y panel de decisiones.
// Los datos vienen de frontend/public/ (JSON grabados).

import { useCallback, useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

import { Icon } from './ui/icons'
import { baseStyle, MTY_CENTER, MTY_ZOOM } from './map/style'
import { createRoadLoader } from './map/roads'
import { addTrailLayers } from './map/trails'
import { actualizarLlegadas } from './map/arrivals'
import { dispararShock, type ShockType } from './map/shocks'

import { cargarTurnosPorSeed, cargarIndiceTurnos, cargarPuntos } from './lib/loader'
import { posicionEnMinuto, minutosAHora, contadoresEnT, estelaHastaT } from './lib/sim'
import type { TurnoData, TurnoIndex } from './lib/turno'
import { Counterfactual } from './sim/Counterfactual'
import { Counters } from './sim/Counters'
import { Decisions } from './sim/Decisions'
import { Distribution } from './sim/Distribution'
import { DecisionToasts } from './sim/DecisionToasts'
import { DecisionHistory } from './sim/DecisionHistory'
import { GeminiBadge, GeminiNote } from './sim/GeminiStatus'
import { VozToggle } from './voice/VozToggle'

maplibregl.setWorkerUrl(maplibreWorkerUrl)

const SPEEDS = [1, 2, 4] as const
const MS_PER_STEP_BASE = 500 // 1 min simulado cada 0.5s a velocidad ×1

export default function SimView() {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const greedyMarker = useRef<maplibregl.Marker | null>(null)
  const nuezMarker = useRef<maplibregl.Marker | null>(null)
  const arrivalMarkers = useRef<Record<string, maplibregl.Marker>>({})

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

  const handleShock = (type: ShockType) => dispararShock(mapRef.current, type)

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

  // Inicializar mapa
  const initMap = useCallback(async () => {
    if (!mapContainer.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: baseStyle(),
      center: MTY_CENTER,
      zoom: MTY_ZOOM,
      pitch: 0,
      bearing: 0,
      maxZoom: 18,
      minZoom: 11,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')

    map.on('load', async () => {
      try {
        const loadNearby = createRoadLoader(map, () => {})
        await loadNearby(MTY_CENTER, 8)
        let debounceTimer: ReturnType<typeof setTimeout>
        map.on('moveend', () => {
          if (map.getZoom() < 11) return
          clearTimeout(debounceTimer)
          debounceTimer = setTimeout(() => {
            const c = map.getCenter()
            loadNearby([c.lng, c.lat], 1)
          }, 300)
        })

        addTrailLayers(map)
      } catch (err) {
        console.error('Error cargando datos del grafo:', err)
      }
    })

    // Crear marcadores
    const mkGreedy = document.createElement('div')
    mkGreedy.className = 'marker-moto is-greedy'
    mkGreedy.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="17" r="3"/><circle cx="19" cy="17" r="3"/><path d="M5 14l3-7h4l3 7"/><path d="M8 7h8l3 10"/></svg>`
    greedyMarker.current = new maplibregl.Marker({ element: mkGreedy })
      .setLngLat(MTY_CENTER)
      .addTo(map)

    const mkNuez = document.createElement('div')
    mkNuez.className = 'marker-moto is-nuez'
    mkNuez.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="17" r="3"/><circle cx="19" cy="17" r="3"/><path d="M5 14l3-7h4l3 7"/><path d="M8 7h8l3 10"/></svg>`
    nuezMarker.current = new maplibregl.Marker({ element: mkNuez }).setLngLat(MTY_CENTER).addTo(map)
  }, [])

  useEffect(() => {
    initMap()
    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [initMap])

  // Actualizar posiciones y estelas cuando cambia `t`
  useEffect(() => {
    const map = mapRef.current
    if (!map || !greedy || !nuez || !puntos) return

    const posG = posicionEnMinuto(t, greedy.tramos, greedy.geometria, greedy.config, puntos)
    const posN = posicionEnMinuto(t, nuez.tramos, nuez.geometria, nuez.config, puntos)

    greedyMarker.current?.setLngLat(posG)
    nuezMarker.current?.setLngLat(posN)

    // Actualizar estelas
    if (map.getSource('trail-greedy')) {
      const trailG = estelaHastaT(t, greedy.tramos, greedy.geometria)
      ;(map.getSource('trail-greedy') as maplibregl.GeoJSONSource).setData(trailG)
    }
    if (map.getSource('trail-nuez')) {
      const trailN = estelaHastaT(t, nuez.tramos, nuez.geometria)
      ;(map.getSource('trail-nuez') as maplibregl.GeoJSONSource).setData(trailN)
    }

    // Marcadores de llegada y siguiente destino
    actualizarLlegadas(map, arrivalMarkers.current, puntos, t, {
      greedy: greedy.frames,
      nuez: nuez.frames,
    })
  }, [t, greedy, nuez, puntos])

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

  let lastDecisionId = undefined;
  if (nuez && nuez.frames) {
    for (let i = Math.min(t, nuez.frames.length - 1); i >= 0; i--) {
      if (nuez.frames[i].decisiones.length > 0) {
        lastDecisionId = `${i}-${nuez.frames[i].decisiones[nuez.frames[i].decisiones.length - 1].oferta_id}`;
        break;
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

      {/* Logo y badge de Gemini (estado real, sondeado de /shift/status) */}
      <div className="logo-container">
        <GeminiBadge />
        <div className="logo" role="img" aria-label="Nuez">
          {Icon.mark}
        </div>
      </div>

      {/* Avisos de decisión: aceptado arriba, bloqueado por seguridad abajo */}
      <DecisionToasts frame={nuez?.frames[t]} seed={seed} t={t} />

      {/* Timeline */}
      <div className="timeline-panel">
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

        {/* Shocks (Disrupciones) */}
        <div
          className="shock-controls"
          style={{
            display: 'flex',
            gap: '8px',
            marginLeft: '16px',
            borderLeft: '1px solid #e2e8f0',
            paddingLeft: '16px',
          }}
        >
          <button
            onClick={() => handleShock('closure')}
            style={{
              padding: '6px 12px',
              fontSize: '0.8rem',
              fontWeight: 600,
              backgroundColor: '#fef3c7',
              color: '#b45309',
              border: '1px solid #fde68a',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            🚧 Cerrar Constitución
          </button>
          <button
            onClick={() => handleShock('rain')}
            style={{
              padding: '6px 12px',
              fontSize: '0.8rem',
              fontWeight: 600,
              backgroundColor: '#e0f2fe',
              color: '#0369a1',
              border: '1px solid #bae6fd',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            🌧 Empezar Lluvia
          </button>
        </div>
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
          <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <DecisionHistory lastDecisionId={lastDecisionId} />
            <div style={{ borderTop: '1px solid var(--surface-high)' }} />
            <Decisions frames={nuez.frames} t={t} horaInicio={horaInicio} />
          </div>
        )}
      </div>
    </div>
  )
}
