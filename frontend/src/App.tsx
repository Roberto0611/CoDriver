import { useCallback, useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

import { Icon } from './ui/icons'
import { ZONAS_LIST } from './lib/zones'
import { baseStyle, MTY_CENTER, MTY_ZOOM } from './map/style'
import { addRouteLayers, toggleTrafficLayer } from './map/layers'
import { attachHoverPopups } from './map/popups'
import { createRoadLoader } from './map/roads'
import { drawRoute, fetchRoute, routeInfoOf, type VSInfo } from './map/route'
import { NaviePlayground } from './navie/NaviePlayground'

// Configurar worker de MapLibre para Vite
maplibregl.setWorkerUrl(maplibreWorkerUrl)

interface GraphStats {
  edges: number
  nodes: number
}

function timeToMinutes(timeStr: string): number {
  const [h, m] = timeStr.split(':').map(Number)
  return (h || 0) * 60 + (m || 0)
}

function minutesToTime(totalMin: number): string {
  const clamped = Math.max(0, Math.min(24 * 60 - 1, totalMin))
  const h = Math.floor(clamped / 60)
    .toString()
    .padStart(2, '0')
  const m = (clamped % 60).toString().padStart(2, '0')
  return `${h}:${m}`
}

function App() {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<{
    origin: maplibregl.Marker | null
    destination: maplibregl.Marker | null
    classicCar: maplibregl.Marker | null
    aiCar: maplibregl.Marker | null
  }>({ origin: null, destination: null, classicCar: null, aiCar: null })
  const [loading, setLoading] = useState(true)
  const [loadingRoute, setLoadingRoute] = useState(false)
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [route, setRoute] = useState<VSInfo | null>(null)
  const [origin, setOrigin] = useState<string>('Centro')
  const [destination, setDestination] = useState<string>('Valle')
  const [showTraffic, setShowTraffic] = useState(false)
  const [currentTime, setCurrentTime] = useState('14:00')
  const [isPlaying, setIsPlaying] = useState(false)
  const isNaviePlayground = typeof window !== 'undefined' && window.location.hash === '#navie'

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
      minZoom: 13,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')

    map.on('load', async () => {
      try {
        const loadNearby = createRoadLoader(map, (edges) => setStats({ edges, nodes: 0 }))
        await loadNearby(MTY_CENTER, 8)
        let debounceTimer: ReturnType<typeof setTimeout>
        map.on('moveend', () => {
          if (map.getZoom() < 11) return // No cargar más calles si está muy alejado
          clearTimeout(debounceTimer)
          debounceTimer = setTimeout(() => {
            const c = map.getCenter()
            loadNearby([c.lng, c.lat], 1) // Cargar solo 1 zona a la vez
          }, 300)
        })

        addRouteLayers(map)
        attachHoverPopups(map)
      } catch (err) {
        console.error('Error cargando datos del grafo:', err)
      } finally {
        setLoading(false)
      }
    })
  }, [])

  useEffect(() => {
    if (isNaviePlayground) return

    initMap()
    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [initMap, isNaviePlayground])

  // Toggle de tráfico: actualizar capa cuando cambia la hora o la visibilidad, o si cargan más calles
  useEffect(() => {
    if (!mapRef.current) return
    toggleTrafficLayer(mapRef.current, showTraffic, currentTime)
  }, [showTraffic, currentTime, stats?.edges])

  // Auto-play: Cada 5 segundos avanza 1 minuto el tiempo de simulación
  useEffect(() => {
    if (!isPlaying) return

    const interval = setInterval(() => {
      setCurrentTime((prev) => {
        const mins = timeToMinutes(prev)
        // Rango de simulación: 14:00 (840) a 16:00 (960)
        const nextMins = mins >= 960 ? 840 : mins + 1
        return minutesToTime(nextMins)
      })
    }, 5000)

    return () => clearInterval(interval)
  }, [isPlaying])

  const stepMinute = (delta: number) => {
    setCurrentTime((prev) => {
      const mins = timeToMinutes(prev)
      const nextMins = Math.max(840, Math.min(960, mins + delta))
      return minutesToTime(nextMins)
    })
  }

  const handleTogglePlay = () => {
    if (!isPlaying && !showTraffic) {
      setShowTraffic(true)
    }
    setIsPlaying((prev) => !prev)
  }

  const fetchDynamicRoute = async () => {
    const map = mapRef.current
    if (!map) return
    setLoadingRoute(true)
    try {
      const data = await fetchRoute(origin, destination, currentTime)
      const info = routeInfoOf(data)
      if (info) {
        setRoute(info)
        drawRoute(map, data, info, markersRef.current)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingRoute(false)
    }
  }

  if (isNaviePlayground) {
    return <NaviePlayground />
  }

  return (
    <div className="app">
      {/* Mapa */}
      <div ref={mapContainer} className="map-container" />

      {/* Loading */}
      <div className={`loading-overlay ${loading ? 'active' : ''}`}>
        <div className="loading-spinner" />
        <div className="loading-text">Loading Monterrey's streets…</div>
      </div>

      {/* Timeline de Tráfico en la parte superior del centro */}
      <div className="timeline-panel">
        <div className="timeline-controls">
          <button
            className="timeline-btn-round"
            title="Atrasar 1 minuto"
            onClick={() => stepMinute(-1)}
          >
            -1
          </button>

          <button
            className="timeline-btn-play"
            title={isPlaying ? 'Pausar simulación' : 'Iniciar simulación (1 min / 5s)'}
            onClick={handleTogglePlay}
          >
            {isPlaying ? Icon.pause : Icon.play}
          </button>

          <button
            className="timeline-btn-round"
            title="Avanzar 1 minuto"
            onClick={() => stepMinute(1)}
          >
            +1
          </button>
        </div>

        <div className="timeline-scrubber">
          <div className="timeline-time-display">{currentTime}</div>

          <div className="timeline-slider-track">
            <input
              type="range"
              min={840}
              max={960}
              step={1}
              value={timeToMinutes(currentTime)}
              onChange={(e) => setCurrentTime(minutesToTime(Number(e.target.value)))}
              className="timeline-slider"
            />
            <div className="timeline-labels">
              <span>14:00</span>
              <span>16:00</span>
            </div>
          </div>
        </div>

        <button
          className={`timeline-toggle-btn ${showTraffic ? 'is-active' : ''}`}
          onClick={() => setShowTraffic(!showTraffic)}
        >
          {showTraffic ? 'Layer: On' : 'Layer: Off'}
        </button>
      </div>

      {/* Logo superior izquierdo */}
      <div className="logo" role="img" aria-label="Nuez">
        {Icon.mark}
      </div>

      {/* Panel de ruta (centro a la izquierda) */}
      <div className="overlay-panel">
        {/* Buscador de rutas */}
        <div className="glass-card finder-card">
          <div className="finder">
            <div
              className="finder-title"
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              {Icon.pin} Simulation Setup
            </div>
            <div className="finder-fields">
              <div className="field">
                <label htmlFor="origin">Origin</label>
                <div className="select">
                  <select id="origin" value={origin} onChange={(e) => setOrigin(e.target.value)}>
                    {ZONAS_LIST.map((z) => (
                      <option key={z} value={z}>
                        {z}
                      </option>
                    ))}
                  </select>
                  {Icon.chevron}
                </div>
              </div>
              <div className="field">
                <label htmlFor="destination">Destination</label>
                <div className="select">
                  <select
                    id="destination"
                    value={destination}
                    onChange={(e) => setDestination(e.target.value)}
                  >
                    {ZONAS_LIST.map((z) => (
                      <option key={z} value={z}>
                        {z}
                      </option>
                    ))}
                  </select>
                  {Icon.chevron}
                </div>
              </div>
            </div>
            <button className="btn-primary" onClick={fetchDynamicRoute} disabled={loadingRoute}>
              {Icon.route}
              {loadingRoute ? 'Running Simulation…' : 'Start Race'}
            </button>
          </div>
        </div>

        {/* Dashboard VS */}
        {route && (
          <div className="vs-dashboard">
            <div
              className="vs-header"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                justifyContent: 'center',
              }}
            >
              {Icon.route} ALGORITHM SHOWDOWN
            </div>

            <div className="vs-cards">
              {/* Classic Agent Card */}
              {route.classic && (
                <div className="glass-card agent-card classic-agent">
                  <div className="agent-header">
                    <span className="agent-icon" style={{ width: '1.2em', height: '1.2em' }}>
                      {Icon.moto}
                    </span>
                    <span className="agent-name">Classic Algorithm</span>
                  </div>
                  <div className="agent-stats">
                    <div className="stat-box">
                      <span className="stat-value">{route.classic.timeMin}</span>
                      <span className="stat-label">mins</span>
                    </div>
                    <div className="stat-box">
                      <span className="stat-value">{route.classic.lengthKm}</span>
                      <span className="stat-label">km</span>
                    </div>
                  </div>
                  <div className="agent-log">
                    <code>[{currentTime}] Route locked. Ignoring live traffic.</code>
                  </div>
                </div>
              )}

              {/* AI Agent Card */}
              {route.ai && (
                <div className="glass-card agent-card ai-agent">
                  <div className="agent-header">
                    <span className="agent-icon" style={{ width: '1.2em', height: '1.2em' }}>
                      {Icon.mark}
                    </span>
                    <span className="agent-name">Nuez AI</span>
                  </div>
                  <div className="agent-stats">
                    <div className="stat-box">
                      <span className="stat-value">{route.ai.timeMin}</span>
                      <span className="stat-label">mins</span>
                    </div>
                    <div className="stat-box">
                      <span className="stat-value">{route.ai.lengthKm}</span>
                      <span className="stat-label">km</span>
                    </div>
                  </div>
                  <div className="agent-log brain-log">
                    <code>
                      {route.ai.timeMin < (route.classic?.timeMin || 0)
                        ? `[${currentTime}] [!] Traffic ahead. Rerouting via optimal path.`
                        : `[${currentTime}] Analyzing traffic... Current path is optimal.`}
                    </code>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
