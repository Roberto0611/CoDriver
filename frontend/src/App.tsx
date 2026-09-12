import { useCallback, useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

import { Icon } from './ui/icons'
import { formatNumber, ZONAS_LIST } from './lib/zones'
import { baseStyle, MTY_CENTER, MTY_ZOOM } from './map/style'
import {
  addPuntosLayer,
  addRoadLayers,
  addRouteLayers,
  addTrafficLayers,
  addZonaLayers,
  toggleTrafficLayer,
} from './map/layers'
import { attachHoverPopups } from './map/popups'
import { createRoadLoader } from './map/roads'
import { drawRoute, fetchRoute, routeInfoOf, type RouteInfo } from './map/route'

// Configurar worker de MapLibre para Vite
maplibregl.setWorkerUrl(maplibreWorkerUrl)

interface GraphStats {
  edges: number
  nodes: number
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
        addTrafficLayers(map)
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

      {/* Panel izquierdo */}
      <div className="overlay-panel">
        {/* Logo */}
        <div className="logo" role="img" aria-label="Nuez">
          {Icon.mark}
        </div>

        {/* Stats */}
        {stats && (
          <div className="glass-card">
            <div className="stats-grid">
              <div className="stat-item">
                <div className="stat-value">{formatNumber(stats.nodes)}</div>
                <div className="stat-label">Nodes</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{formatNumber(stats.edges)}</div>
                <div className="stat-label">Segments</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">
                  20<small>km</small>
                </div>
                <div className="stat-label">Radius</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">5</div>
                <div className="stat-label">Road classes</div>
              </div>
            </div>
          </div>
        )}

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

        {/* Simulador de Tráfico */}
        <div className="glass-card">
          <div className="finder">
            <div className="finder-title">Traffic layer</div>

            <div className="field">
              <label htmlFor="sim-clock">Simulation clock</label>
              <input
                id="sim-clock"
                type="time"
                value={currentTime}
                onChange={(e) => setCurrentTime(e.target.value)}
                className="input-time"
              />
            </div>

            <button
              className={showTraffic ? 'btn-danger' : 'btn-primary'}
              onClick={() => setShowTraffic(!showTraffic)}
            >
              {showTraffic ? 'Hide traffic' : 'Show traffic'}
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

        {/* Leyenda */}
        <div className="glass-card">
          <div className="legend">
            <div className="legend-title">Road classes</div>
            <div className="legend-item">
              <div className="legend-line highway" />
              Highway / trunk
            </div>
            <div className="legend-item">
              <div className="legend-line primary" />
              Primary
            </div>
            <div className="legend-item">
              <div className="legend-line secondary" />
              Secondary
            </div>
            <div className="legend-item">
              <div className="legend-line local" />
              Local / residential
            </div>
            <div className="legend-item">
              <div className="legend-line route" />
              Active route
            </div>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      {stats && (
        <div className="bottom-bar">
          <div className="bottom-pill">
            {Icon.pin} <strong>Monterrey, NL</strong>
          </div>
          <div className="bottom-pill">
            {Icon.map} <strong>{formatNumber(stats.edges)}</strong> road segments
          </div>
          {route && (
            <div className="bottom-pill is-route">
              {Icon.route}{' '}
              <strong>
                {route.from} to {route.to}
              </strong>{' '}
              · {route.lengthKm} km
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
