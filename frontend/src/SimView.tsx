// Reproductor de turnos grabados: dos motos (Greedy vs Nuez) corren el
// mismo turno lado a lado, con contadores de ganancias y panel de decisiones.
// Los datos vienen de frontend/public/ (JSON grabados).

import { useCallback, useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

import { Icon } from './ui/icons'
import { baseStyle, MTY_CENTER, MTY_ZOOM, ROUTE_COLOR } from './map/style'
import { addRouteLayers } from './map/layers'
import { createRoadLoader } from './map/roads'

import { cargarTurnosPorSeed, cargarIndiceTurnos, cargarPuntos } from './lib/loader'
import { posicionEnMinuto, minutosAHora, contadoresEnT, estelaHastaT } from './lib/sim'
import type { TurnoData, TurnoIndex } from './lib/turno'
import { Counters } from './sim/Counters'
import { Decisions } from './sim/Decisions'

maplibregl.setWorkerUrl(maplibreWorkerUrl)

const SPEEDS = [1, 2, 4] as const
const MS_PER_STEP_BASE = 500 // 1 min simulado cada 0.5s a velocidad ×1

// Colores de las estelas (constantes de mapa, MapLibre no lee CSS vars)
const GREEDY_TRAIL = '#F59E0B'  // ámbar
const NUEZ_TRAIL = '#4F46E5'    // índigo

export default function SimView() {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const greedyMarker = useRef<maplibregl.Marker | null>(null)
  const nuezMarker = useRef<maplibregl.Marker | null>(null)

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

        // Fuentes para estelas
        map.addSource('trail-greedy', {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] },
        })
        map.addSource('trail-nuez', {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] },
        })

        map.addLayer({
          id: 'trail-greedy-line',
          type: 'line',
          source: 'trail-greedy',
          paint: {
            'line-color': GREEDY_TRAIL,
            'line-width': 3,
            'line-opacity': 0.5,
          },
          layout: { 'line-cap': 'round', 'line-join': 'round' },
        })
        map.addLayer({
          id: 'trail-nuez-casing',
          type: 'line',
          source: 'trail-nuez',
          paint: {
            'line-color': '#FFFFFF',
            'line-width': 5,
            'line-opacity': 0.6,
          },
          layout: { 'line-cap': 'round', 'line-join': 'round' },
        })
        map.addLayer({
          id: 'trail-nuez-line',
          type: 'line',
          source: 'trail-nuez',
          paint: {
            'line-color': NUEZ_TRAIL,
            'line-width': 3,
            'line-opacity': 0.8,
          },
          layout: { 'line-cap': 'round', 'line-join': 'round' },
        })
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
    nuezMarker.current = new maplibregl.Marker({ element: mkNuez })
      .setLngLat(MTY_CENTER)
      .addTo(map)
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

  const greedyCounters = greedy ? contadoresEnT(greedy.frames, t) : { ganado: 0, entregas: 0, saltadas: 0 }
  const nuezCounters = nuez ? contadoresEnT(nuez.frames, t) : { ganado: 0, entregas: 0, saltadas: 0 }
  const terminado = t >= maxT - 1

  const currentEntry = indice?.turnos.find((e) => e.seed === seed)

  return (
    <div className="app">
      {/* Mapa */}
      <div ref={mapContainer} className="map-container" />

      {/* Loading */}
      <div className={`loading-overlay ${loading ? 'active' : ''}`}>
        <div className="loading-spinner" />
        <div className="loading-text">Loading shift…</div>
      </div>

      {/* Logo */}
      <div className="logo" role="img" aria-label="Nuez">
        {Icon.mark}
      </div>

      {/* Timeline */}
      <div className="timeline-panel">
        <div className="timeline-controls">
          <button
            className="timeline-btn-round"
            title="Back 1 min"
            onClick={() => stepMinute(-1)}
          >
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
        </div>
      </div>

      {/* Panel izquierdo */}
      <div className="overlay-panel">
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
                      {entry.delta_pct >= 0 ? '+' : ''}{entry.delta_pct.toFixed(0)}%
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

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
          </div>
        )}

        {/* Decisiones */}
        {nuez && (
          <div className="glass-card">
            <Decisions
              frames={nuez.frames}
              t={t}
              horaInicio={horaInicio}
            />
          </div>
        )}
      </div>
    </div>
  )
}
