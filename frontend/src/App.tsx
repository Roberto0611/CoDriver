import { useCallback, useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

// Configurar worker de MapLibre para Vite
maplibregl.setWorkerUrl(maplibreWorkerUrl)

// Centro de Monterrey
const MTY_CENTER: [number, number] = [-100.3161, 25.6866]
const MTY_ZOOM = 14



const ROUTE_COLOR = '#ff3b30'

const ZONAS_LIST = [
  "Centro", "Obispado", "Valle", "Contry", "Tec", "Fundidora", 
  "Guadalupe", "LindaVista", "SanNicolas", "Cumbres", "Mitras", 
  "Escobedo", "SantaCatarina", "Apodaca"
]

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
  const originMarkerRef = useRef<maplibregl.Marker | null>(null)
  const destMarkerRef = useRef<maplibregl.Marker | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingRoute, setLoadingRoute] = useState(false)
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [route, setRoute] = useState<RouteInfo | null>(null)
  const [origin, setOrigin] = useState<string>("Centro")
  const [destination, setDestination] = useState<string>("Valle")
  const [showTraffic, setShowTraffic] = useState(false)
  const [currentTime, setCurrentTime] = useState("14:00")

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
        // Source de la red vial vacío inicialmente
        map.addSource('road-network', {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] },
        })

        // Variables capturadas en el closure para el lazy loading
        const loadedZones = new Set<string>()
        let allRoadFeatures: any[] = []
        let loadingZones = false

        const loadNearbyZones = async (center: [number, number], count: number) => {
          if (loadingZones) return
          loadingZones = true
          try {
            // Obtenemos centros de zonas
            const zonasRes = await fetch('/zonas.json')
            const zonasData = await zonasRes.json()
            
            const dists = zonasData.features.map((f: any) => {
              const c = f.properties.centro
              const dist = Math.pow(c[0] - center[0], 2) + Math.pow(c[1] - center[1], 2)
              return { zona: f.properties.zona, dist }
            })
            
            dists.sort((a: any, b: any) => a.dist - b.dist)
            
            let newFeatures = false
            for (const { zona } of dists) {
              if (loadedZones.has(zona)) continue
              if (count <= 0) break
              count--
              
              console.log(`[Copiloto] Descargando calles para zona: ${zona}`)
              loadedZones.add(zona)
              const res = await fetch(`/mty_edges_${zona}.json`)
              if (res.ok) {
                const data = await res.json()
                allRoadFeatures = allRoadFeatures.concat(data.features)
                newFeatures = true
              }
            }
            
            if (newFeatures && map.getSource('road-network')) {
              const source = map.getSource('road-network') as maplibregl.GeoJSONSource
              source.setData({
                type: 'FeatureCollection',
                features: allRoadFeatures
              })
              setStats({ edges: allRoadFeatures.length, nodes: 0 }) // Opcional: calcular nodos
            }
          } catch (e) {
            console.error("Error lazy loading", e)
          } finally {
            loadingZones = false
          }
        }

        // Carga inicial
        await loadNearbyZones(MTY_CENTER, 5)

        // Escuchar cuando el usuario mueve el mapa para cargar más
        map.on('moveend', () => {
          const c = map.getCenter()
          loadNearbyZones([c.lng, c.lat], 2)
        })

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

        // Cargar ruta de ejemplo inicial vacía o default
        const routeData = { type: 'FeatureCollection', features: [] }
        map.addSource('route', { type: 'geojson', data: routeData as any })

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

        // Layer de Tráfico e Incidentes
        map.addSource('traffic', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
        
        map.addLayer({
          id: 'traffic-line',
          type: 'line',
          source: 'traffic',
          filter: ['==', ['get', 'tipo'], 'TRAFICO'],
          paint: {
            'line-color': [
              'interpolate',
              ['linear'],
              ['get', 'factor_retraso'],
              1.0, '#22c55e', // Verde (fluido)
              1.5, '#eab308', // Amarillo (moderado)
              2.5, '#f97316', // Naranja (pesado)
              4.0, '#ef4444'  // Rojo (muy pesado)
            ],
            'line-width': ['interpolate', ['linear'], ['zoom'], 9, 3, 14, 8],
            'line-opacity': 0.85
          },
          layout: { 'line-cap': 'round', 'line-join': 'round', 'visibility': 'none' }
        })

        map.addLayer({
          id: 'traffic-incident',
          type: 'line',
          source: 'traffic',
          filter: ['==', ['get', 'tipo'], 'CIERRE_TOTAL'],
          paint: {
            'line-color': '#000000',
            'line-width': ['interpolate', ['linear'], ['zoom'], 9, 4, 14, 10],
            'line-dasharray': [1, 2]
          },
          layout: { 'line-cap': 'round', 'line-join': 'round', 'visibility': 'none' }
        })

        // Cargar zonas
        const zonasRes = await fetch('/zonas.json')
        const zonasData = await zonasRes.json()

        map.addSource('zonas', { type: 'geojson', data: zonasData })

        // Usar una expresión match para asignar colores únicos a cada zona
        const zonaColors = [
          'match', ['get', 'zona'],
          'Centro', '#3b82f6',
          'Obispado', '#10b981',
          'Valle', '#8b5cf6',
          'Contry', '#f59e0b',
          'Tec', '#ec4899',
          'Fundidora', '#ef4444',
          'Guadalupe', '#14b8a6',
          'LindaVista', '#f97316',
          'SanNicolas', '#06b6d4',
          'Cumbres', '#6366f1',
          'Mitras', '#d946ef',
          'Escobedo', '#84cc16',
          'SantaCatarina', '#0ea5e9',
          'Apodaca', '#f43f5e',
          '#64748b' // default
        ]

        map.addLayer({
          id: 'zonas-fill',
          type: 'fill',
          source: 'zonas',
          paint: {
            'fill-color': zonaColors as any,
            'fill-opacity': 0.15
          }
        }) // Renderizar arriba de las calles para no perder el hover

        map.addLayer({
          id: 'zonas-line',
          type: 'line',
          source: 'zonas',
          paint: {
            'line-color': zonaColors as any,
            'line-width': 2,
            'line-opacity': 0.8
          }
        })

        // Cargar puntos
        const puntosRes = await fetch('/puntos.json')
        const puntosData = await puntosRes.json()

        map.addSource('puntos', { type: 'geojson', data: puntosData })

        map.addLayer({
          id: 'puntos-circle',
          type: 'circle',
          source: 'puntos',
          paint: {
            'circle-color': '#ffffff',
            'circle-radius': 3,
            'circle-opacity': 0.6,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#000000'
          }
        })

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

        // Hover interactivo para zonas
        map.on('mouseenter', 'zonas-fill', (e) => {
          map.getCanvas().style.cursor = 'pointer'
          const props = e.features?.[0]?.properties
          if (!props) return

          popup
            .setLngLat(e.lngLat)
            .setHTML(`
              <strong>Zona: ${props.zona}</strong><br>
              <span style="color:#8a8a9a">Riesgo Día:</span> ${props.riesgo_dia}<br>
              <span style="color:#8a8a9a">Riesgo Noche:</span> ${props.riesgo_noche}<br>
              <span style="color:#8a8a9a">Bloqueada Noche:</span> ${props.bloqueada_noche ? 'Sí' : 'No'}
            `)
            .addTo(map)
        })

        map.on('mouseleave', 'zonas-fill', () => {
          map.getCanvas().style.cursor = ''
          popup.remove()
        })

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

  useEffect(() => {
    if (!mapRef.current) return
    const map = mapRef.current
    
    // Toggle visibility
    if (map.getLayer('traffic-line')) {
      map.setLayoutProperty('traffic-line', 'visibility', showTraffic ? 'visible' : 'none')
      map.setLayoutProperty('traffic-incident', 'visibility', showTraffic ? 'visible' : 'none')
    }

    if (showTraffic) {
      // Fetch traffic data for the current time
      fetch(`http://127.0.0.1:8000/api/traffic?hora=${currentTime}`)
        .then(r => r.json())
        .then(data => {
          const source = map.getSource('traffic') as maplibregl.GeoJSONSource
          if (source) {
            source.setData(data.geojson)
          }
        })
        .catch(console.error)
    }
  }, [showTraffic, currentTime])

  const fetchDynamicRoute = async () => {
    if (!mapRef.current) return
    setLoadingRoute(true)
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/route?origen=${origin}&destino=${destination}&hora=${currentTime}`)
      if (!res.ok) throw new Error("Error fetching route")
      const routeData = await res.json()

      if (routeData.features.length > 0) {
        const props = routeData.features[0].properties
        setRoute({
          from: props.from,
          to: props.to,
          lengthKm: props.length_km,
          timeMin: props.time_min,
          nodes: props.nodes,
        })

        const map = mapRef.current
        const source = map.getSource('route') as maplibregl.GeoJSONSource
        if (source) {
          source.setData(routeData)
        }

        const routeCoords = routeData.features[0].geometry.coordinates
        const originCoord = routeCoords[0]
        const destinationCoord = routeCoords[routeCoords.length - 1]

        if (originMarkerRef.current) originMarkerRef.current.remove()
        if (destMarkerRef.current) destMarkerRef.current.remove()

        const originEl = document.createElement('div')
        originEl.style.cssText = `
          width: 14px; height: 14px; border-radius: 50%;
          background: ${ROUTE_COLOR}; border: 2px solid #fff;
          box-shadow: 0 0 12px ${ROUTE_COLOR}88;
        `
        originMarkerRef.current = new maplibregl.Marker({ element: originEl })
          .setLngLat(originCoord as [number, number])
          .setPopup(new maplibregl.Popup({ offset: 12 }).setHTML(`<strong>📍 ${origin}</strong><br><span style="color:#8a8a9a">Origen</span>`))
          .addTo(map)

        const destEl = document.createElement('div')
        destEl.style.cssText = `
          width: 14px; height: 14px; border-radius: 50%;
          background: transparent; border: 3px solid ${ROUTE_COLOR};
          box-shadow: 0 0 12px ${ROUTE_COLOR}88;
        `
        destMarkerRef.current = new maplibregl.Marker({ element: destEl })
          .setLngLat(destinationCoord as [number, number])
          .setPopup(new maplibregl.Popup({ offset: 12 }).setHTML(`<strong>📍 ${destination}</strong><br><span style="color:#8a8a9a">Destino</span>`))
          .addTo(map)

        // Fit bounds
        const bounds = new maplibregl.LngLatBounds()
        routeCoords.forEach((c: any) => bounds.extend(c))
        map.fitBounds(bounds, { padding: 50, duration: 1000 })
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingRoute(false)
    }
  }

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

        {/* Buscador de rutas */}
        <div className="glass-card">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '14px', fontWeight: 'bold' }}>Trazar Ruta</div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
              <label style={{ fontSize: '12px', color: '#a1a1aa' }}>Origen:</label>
              <select 
                value={origin} 
                onChange={(e) => setOrigin(e.target.value)}
                style={{ background: '#18181b', color: 'white', border: '1px solid #3f3f46', padding: '6px', borderRadius: '4px' }}
              >
                {ZONAS_LIST.map(z => <option key={z} value={z}>{z}</option>)}
              </select>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
              <label style={{ fontSize: '12px', color: '#a1a1aa' }}>Destino:</label>
              <select 
                value={destination} 
                onChange={(e) => setDestination(e.target.value)}
                style={{ background: '#18181b', color: 'white', border: '1px solid #3f3f46', padding: '6px', borderRadius: '4px' }}
              >
                {ZONAS_LIST.map(z => <option key={z} value={z}>{z}</option>)}
              </select>
            </div>

            <button 
              onClick={fetchDynamicRoute}
              disabled={loadingRoute}
              style={{
                background: '#3b82f6', color: 'white', border: 'none', padding: '8px', 
                borderRadius: '4px', cursor: loadingRoute ? 'not-allowed' : 'pointer',
                marginTop: '5px', fontWeight: 'bold'
              }}
            >
              {loadingRoute ? 'Calculando...' : 'Trazar Ruta'}
            </button>
          </div>
        </div>

        {/* Simulador de Tráfico */}
        <div className="glass-card">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ fontSize: '14px', fontWeight: 'bold' }}>Capa de Tráfico</div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <label style={{ fontSize: '12px', color: '#a1a1aa' }}>Reloj Simulación:</label>
              <input 
                type="time" 
                value={currentTime} 
                onChange={(e) => setCurrentTime(e.target.value)}
                style={{ background: '#18181b', color: 'white', border: '1px solid #3f3f46', padding: '4px', borderRadius: '4px' }}
              />
            </div>

            <button 
              onClick={() => setShowTraffic(!showTraffic)}
              style={{
                background: showTraffic ? '#ef4444' : '#22c55e', color: 'white', border: 'none', padding: '8px', 
                borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold'
              }}
            >
              {showTraffic ? 'Ocultar Tráfico' : 'Ver Tráfico'}
            </button>
          </div>
        </div>

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
