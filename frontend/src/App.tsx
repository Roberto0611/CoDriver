import { useCallback, useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

// Configurar worker de MapLibre para Vite
maplibregl.setWorkerUrl(maplibreWorkerUrl)

// Centro de Monterrey
const MTY_CENTER: [number, number] = [-100.3161, 25.6866]
const MTY_ZOOM = 14

// Colores por tipo de vía (coherente con el CSS)
const ROAD_COLORS: Record<string, string> = {
  highway: '#fbbf24',
  primary: '#94a3b8',
  secondary: '#64748b',
  tertiary: '#475569',
  local: '#334155',
}

const ROUTE_COLOR = '#ff3b30'

interface GraphStats {
  edges: number
  nodes: number
}

interface RouteInfo {
  from: string
  to: string
  lengthKm: number
  timeMin: number
  nodes: number
}

function App() {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [route, setRoute] = useState<RouteInfo | null>(null)

  const initMap = useCallback(async () => {
    if (!mapContainer.current || mapRef.current) return

    // Inicializar mapa con estilo oscuro vacío
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        name: 'MTY Dark',
        sources: {},
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: { 'background-color': '#0a0a0f' },
          },
        ],
        glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
      },
      center: MTY_CENTER,
      zoom: MTY_ZOOM,
      pitch: 0,
      bearing: 0,
      maxZoom: 18,
      minZoom: 9,
    })

    mapRef.current = map

    // Controles
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')

    map.on('load', async () => {
      try {
        // Cargar red vial
        const edgesRes = await fetch('/mty_edges.json')
        const edgesData = await edgesRes.json()

        setStats({
          edges: edgesData.features.length,
          nodes: 0, // Se calcula abajo
        })

        // Contar nodos únicos (aproximado por coordenadas)
        const nodeSet = new Set<string>()
        for (const f of edgesData.features) {
          const coords = f.geometry.coordinates
          if (coords.length > 0) {
            nodeSet.add(`${coords[0][0]},${coords[0][1]}`)
            nodeSet.add(`${coords[coords.length - 1][0]},${coords[coords.length - 1][1]}`)
          }
        }
        setStats({ edges: edgesData.features.length, nodes: nodeSet.size })

        // Source de la red vial
        map.addSource('road-network', {
          type: 'geojson',
          data: edgesData,
        })

        console.log(`[Copiloto] Grafo cargado: ${edgesData.features.length} aristas`)

        // ── Capas por tipo de vía ────────────────────────────────────────
        // Autopistas/troncales
        map.addLayer({
          id: 'roads-highway',
          type: 'line',
          source: 'road-network',
          filter: ['==', ['get', 'class'], 'highway'],
          paint: {
            'line-color': '#fbbf24',
            'line-width': ['interpolate', ['linear'], ['zoom'], 9, 1.5, 13, 4, 17, 8],
            'line-opacity': ['interpolate', ['linear'], ['zoom'], 9, 0.9, 13, 1],
          },
          layout: { 'line-cap': 'round', 'line-join': 'round' },
        })

        // Primarias
        map.addLayer({
          id: 'roads-primary',
          type: 'line',
          source: 'road-network',
          filter: ['==', ['get', 'class'], 'primary'],
          paint: {
            'line-color': '#e2e8f0',
            'line-width': ['interpolate', ['linear'], ['zoom'], 9, 0.8, 13, 3, 17, 6],
            'line-opacity': ['interpolate', ['linear'], ['zoom'], 9, 0.75, 13, 1],
          },
          layout: { 'line-cap': 'round', 'line-join': 'round' },
        })

        // Secundarias
        map.addLayer({
          id: 'roads-secondary',
          type: 'line',
          source: 'road-network',
          filter: ['==', ['get', 'class'], 'secondary'],
          paint: {
            'line-color': '#94a3b8',
            'line-width': ['interpolate', ['linear'], ['zoom'], 11, 0.5, 13, 2, 17, 5],
            'line-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0.6, 13, 0.9],
          },
          layout: { 'line-cap': 'round', 'line-join': 'round' },
        })

        // Terciarias
        map.addLayer({
          id: 'roads-tertiary',
          type: 'line',
          source: 'road-network',
          filter: ['==', ['get', 'class'], 'tertiary'],
          paint: {
            'line-color': '#64748b',
            'line-width': ['interpolate', ['linear'], ['zoom'], 13, 0.5, 15, 2, 17, 4],
            'line-opacity': ['interpolate', ['linear'], ['zoom'], 13, 0.6, 15, 0.85],
          },
          layout: { 'line-cap': 'round', 'line-join': 'round' },
        })

        // Locales/residenciales (224K features — 83% del grafo)
        map.addLayer({
          id: 'roads-local',
          type: 'line',
          source: 'road-network',
          filter: ['==', ['get', 'class'], 'local'],
          paint: {
            'line-color': '#475569',
            'line-width': ['interpolate', ['linear'], ['zoom'], 14, 0.4, 16, 1.5, 17, 3],
            'line-opacity': ['interpolate', ['linear'], ['zoom'], 14, 0.5, 16, 0.75],
          },
          layout: { 'line-cap': 'round', 'line-join': 'round' },
        })

        // Cargar ruta de ejemplo
        const routeRes = await fetch('/mty_route.json')
        const routeData = await routeRes.json()

        if (routeData.features.length > 0) {
          const props = routeData.features[0].properties
          setRoute({
            from: props.from,
            to: props.to,
            lengthKm: props.length_km,
            timeMin: props.time_min,
            nodes: props.nodes,
          })

          // Glow de la ruta (ancho, difuso)
          map.addSource('route', { type: 'geojson', data: routeData })

          map.addLayer({
            id: 'route-glow',
            type: 'line',
            source: 'route',
            paint: {
              'line-color': ROUTE_COLOR,
              'line-width': [
                'interpolate', ['linear'], ['zoom'],
                9, 4,
                14, 12,
              ],
              'line-opacity': 0.25,
              'line-blur': 6,
            },
            layout: { 'line-cap': 'round', 'line-join': 'round' },
          })

          // Línea principal de la ruta
          map.addLayer({
            id: 'route-line',
            type: 'line',
            source: 'route',
            paint: {
              'line-color': ROUTE_COLOR,
              'line-width': [
                'interpolate', ['linear'], ['zoom'],
                9, 2,
                14, 5,
              ],
              'line-opacity': 0.9,
            },
            layout: { 'line-cap': 'round', 'line-join': 'round' },
          })

          // Marcadores de origen y destino
          const routeCoords = routeData.features[0].geometry.coordinates
          const origin = routeCoords[0]
          const destination = routeCoords[routeCoords.length - 1]

          // Origen
          const originEl = document.createElement('div')
          originEl.style.cssText = `
            width: 14px; height: 14px; border-radius: 50%;
            background: ${ROUTE_COLOR}; border: 2px solid #fff;
            box-shadow: 0 0 12px ${ROUTE_COLOR}88;
          `
          new maplibregl.Marker({ element: originEl })
            .setLngLat(origin as [number, number])
            .setPopup(new maplibregl.Popup({ offset: 12 }).setHTML(
              `<strong>📍 Macroplaza</strong><br><span style="color:#8a8a9a">Origen</span>`
            ))
            .addTo(map)

          // Destino
          const destEl = document.createElement('div')
          destEl.style.cssText = `
            width: 14px; height: 14px; border-radius: 50%;
            background: transparent; border: 3px solid ${ROUTE_COLOR};
            box-shadow: 0 0 12px ${ROUTE_COLOR}88;
          `
          new maplibregl.Marker({ element: destEl })
            .setLngLat(destination as [number, number])
            .setPopup(new maplibregl.Popup({ offset: 12 }).setHTML(
              `<strong>📍 Valle, San Pedro</strong><br><span style="color:#8a8a9a">Destino</span>`
            ))
            .addTo(map)
        }

        // Hover interactivo en carreteras
        const popup = new maplibregl.Popup({
          closeButton: false,
          closeOnClick: false,
          offset: 10,
        })

        const ROAD_LAYERS = ['roads-highway', 'roads-primary', 'roads-secondary', 'roads-tertiary', 'roads-local']

        for (const layerId of ROAD_LAYERS) {
          map.on('mouseenter', layerId, (e) => {
            map.getCanvas().style.cursor = 'pointer'
            const props = e.features?.[0]?.properties
            if (!props) return

            const name = props.name || 'Sin nombre'
            const speed = props.speed ? `${props.speed} km/h` : '—'
            const cls = props.class || 'local'

            popup
              .setLngLat(e.lngLat)
              .setHTML(`
                <strong>${name}</strong><br>
                <span style="color:#8a8a9a">Tipo:</span> ${cls}<br>
                <span style="color:#8a8a9a">Velocidad:</span> ${speed}
              `)
              .addTo(map)
          })

          map.on('mouseleave', layerId, () => {
            map.getCanvas().style.cursor = ''
            popup.remove()
          })
        }

        setLoading(false)
      } catch (err) {
        console.error('Error cargando datos del grafo:', err)
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

  const formatNumber = (n: number) => n.toLocaleString('es-MX')

  return (
    <div className="app">
      {/* Mapa */}
      <div ref={mapContainer} className="map-container" />

      {/* Loading */}
      <div className={`loading-overlay ${loading ? 'active' : ''}`}>
        <div className="loading-spinner" />
        <div className="loading-text">Cargando grafo de Monterrey…</div>
      </div>

      {/* Panel izquierdo */}
      <div className="overlay-panel">
        {/* Header */}
        <div className="glass-card">
          <div className="header">
            <div className="header-icon">🛵</div>
            <div className="header-text">
              <h1>El Copiloto</h1>
              <p>Red vial de Monterrey · OSMnx</p>
            </div>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="glass-card">
            <div className="stats-grid">
              <div className="stat-item">
                <div className="stat-value">{formatNumber(stats.nodes)}</div>
                <div className="stat-label">Nodos</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{formatNumber(stats.edges)}</div>
                <div className="stat-label">Aristas</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">20 km</div>
                <div className="stat-label">Radio</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">5</div>
                <div className="stat-label">Tipos de vía</div>
              </div>
            </div>
          </div>
        )}

        {/* Ruta */}
        {route && (
          <div className="glass-card">
            <div className="route-info">
              <div className="route-header">
                <div className="route-dot" />
                Ruta de ejemplo
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
                  {route.lengthKm}<span>km</span>
                </div>
                <div className="route-stat">
                  {route.timeMin}<span>min</span>
                </div>
                <div className="route-stat">
                  {route.nodes}<span>nodos</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Leyenda */}
        <div className="glass-card">
          <div className="legend">
            <div className="legend-title">Tipos de vía</div>
            <div className="legend-item">
              <div className="legend-line highway" />
              Autopista / Troncal
            </div>
            <div className="legend-item">
              <div className="legend-line primary" />
              Primaria
            </div>
            <div className="legend-item">
              <div className="legend-line secondary" />
              Secundaria
            </div>
            <div className="legend-item">
              <div className="legend-line local" />
              Local / Residencial
            </div>
            <div className="legend-item">
              <div className="legend-line route" />
              Ruta activa
            </div>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      {stats && (
        <div className="bottom-bar">
          <div className="bottom-pill">
            📍 <strong>Monterrey, NL</strong>
          </div>
          <div className="bottom-pill">
            🗺️ <strong>{formatNumber(stats.edges)}</strong> segmentos viales
          </div>
          {route && (
            <div className="bottom-pill">
              🔴 <strong>{route.from} → {route.to}</strong> · {route.lengthKm} km
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
