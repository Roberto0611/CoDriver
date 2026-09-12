import { useCallback, useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

import { Icon } from './ui/icons'
import { formatNumber, ZONAS_LIST } from './lib/zones'
import { baseStyle, MTY_CENTER, MTY_ZOOM } from './map/style'
import { addPuntosLayer, addRoadLayers, addRouteLayers, addZonaLayers, toggleTrafficLayer } from './map/layers'
import { attachHoverPopups } from './map/popups'
import { createRoadLoader } from './map/roads'
import { drawRoute, fetchRoute, routeInfoOf, type RouteInfo } from './map/route'

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
  const h = Math.floor(clamped / 60).toString().padStart(2, '0')
  const m = (clamped % 60).toString().padStart(2, '0')
  return `${h}:${m}`
}

function App() {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<{
    origin: maplibregl.Marker | null
    destination: maplibregl.Marker | null
  }>({ origin: null, destination: null })
  const [loading, setLoading] = useState(true)
  const [loadingRoute, setLoadingRoute] = useState(false)
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [route, setRoute] = useState<RouteInfo | null>(null)
  const [origin, setOrigin] = useState<string>('Centro')
  const [destination, setDestination] = useState<string>('Valle')
  const [showTraffic, setShowTraffic] = useState(false)
  const [currentTime, setCurrentTime] = useState('14:00')
  const [isPlaying, setIsPlaying] = useState(false)

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
      minZoom: 9,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')

    map.on('load', async () => {
      try {
        addRoadLayers(map)
        const loadNearby = createRoadLoader(map, (edges) => setStats({ edges, nodes: 0 }))
        await loadNearby(MTY_CENTER, 5)
        map.on('moveend', () => {
          const c = map.getCenter()
          loadNearby([c.lng, c.lat], 2)
        })

        addRouteLayers(map)
        addZonaLayers(map, await (await fetch('/zonas.json')).json())
        addPuntosLayer(map, await (await fetch('/puntos.json')).json())
        attachHoverPopups(map)
      } catch (err) {
        console.error('Error cargando datos del grafo:', err)
      } finally {
        setLoading(false)
      }
    })
  }, [])

  useEffect(() => {
    initMap()
    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [initMap])

  // Toggle de tráfico: actualizar capa cuando cambia la hora o la visibilidad
  useEffect(() => {
    if (!mapRef.current) return
    toggleTrafficLayer(mapRef.current, showTraffic, currentTime)
  }, [showTraffic, currentTime])

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
        <div className="glass-card">

          <div className="finder">
            <div className="finder-title">Trace a route</div>

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

            <button className="btn-primary" onClick={fetchDynamicRoute} disabled={loadingRoute}>
              {Icon.route}
              {loadingRoute ? 'Routing…' : 'Trace route'}
            </button>
          </div>
        </div>


        {/* Ruta */}
        {route && (
          <div className="glass-card">
            <div className="route-info">
              <div className="route-header">
                <div className="route-dot" />
                Fastest route
              </div>
              <div className="route-endpoints">
                <div className="route-endpoint">
                  <div className="route-endpoint-marker origin" />
                  {route.from}
                </div>
                <div className="route-connector" />
                <div className="route-endpoint">
                  <div className="route-endpoint-marker destination" />
                  {route.to}
                </div>
              </div>
              <div className="route-stats">
                <div className="route-stat">
                  {route.lengthKm}
                  <span>km</span>
                </div>
                <div className="route-stat">
                  {route.timeMin}
                  <span>min</span>
                </div>
                <div className="route-stat">
                  {route.nodes}
                  <span>nodes</span>
                </div>
              </div>
            </div>
          </div>
        )}


      </div>

    </div>
  )
}

export default App
