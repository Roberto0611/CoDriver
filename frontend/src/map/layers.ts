import type { ExpressionSpecification, GeoJSONSource, Map as MLMap } from 'maplibre-gl'
import { ROAD, ROUND, ROUTE_CASING, ROUTE_COLOR } from './style'

const EMPTY = { type: 'FeatureCollection' as const, features: [] }



const zoomWidth = (...stops: number[]): ExpressionSpecification => [
  'interpolate',
  ['linear'],
  ['zoom'],
  ...stops,
]

/**
 * Capas por tipo de vía para una zona específica.
 */
export function addRoadLayers(map: MLMap, zone: string, data: GeoJSON) {
  const sourceId = `road-network-${zone}`
  map.addSource(sourceId, { type: 'geojson', data })

  const beforeId = map.getLayer('route') ? 'route' : undefined

  const road = (
    baseId: string,
    cls: string,
    color: string,
    width: ExpressionSpecification,
    minzoom?: number
  ) => {
    const layer: any = {
      id: `${baseId}-${zone}`,
      type: 'line',
      source: sourceId,
      filter: ['==', ['get', 'class'], cls],
      paint: { 'line-color': color, 'line-width': width },
      layout: ROUND,
    }
    if (minzoom !== undefined) layer.minzoom = minzoom
    map.addLayer(layer, beforeId)
  }

  // Locales/residenciales (224K features — 83% del grafo)
  map.addLayer({
    id: `roads-local-${zone}`,
    type: 'line',
    source: sourceId,
    minzoom: 13.5,
    filter: ['==', ['get', 'class'], 'local'],
    paint: {
      'line-color': ROAD.local,
      'line-width': zoomWidth(14, 0.6, 16, 1.6, 17, 3),
      'line-opacity': zoomWidth(14, 0.6, 16, 1),
    },
    layout: ROUND,
  }, beforeId)

  road('roads-tertiary', 'tertiary', ROAD.tertiary, zoomWidth(13, 0.8, 15, 2.2, 17, 4.5), 12.5)
  road('roads-secondary', 'secondary', ROAD.secondary, zoomWidth(11, 0.8, 13, 2.2, 17, 5.5), 11)
  road(
    'roads-primary-casing',
    'primary',
    ROAD.primaryCasing,
    zoomWidth(9, 1.6, 13, 4.4, 17, 8.4),
    8
  )
  road('roads-primary', 'primary', ROAD.primary, zoomWidth(9, 1, 13, 3, 17, 6.4), 8)
  road('roads-highway-casing', 'highway', ROAD.highwayCasing, zoomWidth(9, 2.4, 13, 5.6, 17, 10.4))
  road('roads-highway', 'highway', ROAD.highway, zoomWidth(9, 1.5, 13, 4, 17, 8))
}

/** Ruta: un borde blanco fino la separa de las calles, sin glow. */
export function addRouteLayers(map: MLMap) {
  map.addSource('route', { type: 'geojson', data: EMPTY })
  map.addLayer({
    id: 'route-casing',
    type: 'line',
    source: 'route',
    paint: { 'line-color': ROUTE_CASING, 'line-width': zoomWidth(9, 5, 14, 9) },
    layout: ROUND,
  })
  map.addLayer({
    id: 'route-line',
    type: 'line',
    source: 'route',
    paint: { 'line-color': ROUTE_COLOR, 'line-width': zoomWidth(9, 2.5, 14, 5) },
    layout: ROUND,
  })
}

// ── Tráfico ──────────────────────────────────────────────────────────────

const TRAFFIC_API = 'http://127.0.0.1:8000'

/** Colores de tráfico para las calles reales (verde → rojo). */
const TRAFFIC_COLOR: ExpressionSpecification = [
  'case',
  ['has', 'traffic_factor'],
  [
    'interpolate',
    ['linear'],
    ['get', 'traffic_factor'],
    1.0,
    '#16a34a', // verde — fluido
    1.3,
    '#eab308', // amarillo — moderado
    1.6,
    '#f97316', // naranja — pesado
    2.0,
    '#ef4444', // rojo — muy pesado
    100,
    '#7f1d1d', // rojo oscuro — cierre/incidente
  ] as unknown as ExpressionSpecification,
  // Fallback: el color propio de la calle segun su clase. Se resuelve dentro de
  // la expresion de MapLibre en vez de escribir una propiedad en cada feature,
  // que con 268k features es memoria que no hace falta gastar.
  [
    'match',
    ['get', 'class'],
    'highway',
    ROAD.highway,
    'primary',
    ROAD.primary,
    'secondary',
    ROAD.secondary,
    'tertiary',
    ROAD.tertiary,
    ROAD.local,
  ],
]

// Colores base por clase de vía (para restaurar al apagar tráfico)
const BASE_COLORS: Record<string, string> = {
  highway: ROAD.highway,
  primary: ROAD.primary,
  secondary: ROAD.secondary,
  tertiary: ROAD.tertiary,
  local: ROAD.local,
}

export function toggleTrafficLayer(
  map: MLMap,
  visible: boolean,
  hora?: string,
  onDone?: () => void
) {
  // Encontrar todas las capas de calles activas
  const getRoadLayers = () => map.getStyle()?.layers?.filter((l) => l.id.startsWith('roads-') && !l.id.includes('-casing')) || []

  if (!visible) {
    // Restaurar colores originales
    for (const layer of getRoadLayers()) {
      // Extraer clase base (ej. 'roads-primary-Centro' -> 'primary')
      const match = layer.id.match(/^roads-([^-]+)/)
      const cls = match ? match[1] : ''
      const color = BASE_COLORS[cls]
      if (color) {
        map.setPaintProperty(layer.id, 'line-color', color)
      }
    }
    onDone?.()
    return
  }

  // Fetch traffic data y colorear calles reales
  fetch(`${TRAFFIC_API}/api/traffic?hora=${hora ?? '14:00'}`)
    .then((r) => r.json())
    .then(
      (data: {
        traffic_map: Record<string, number>
        incidents: Array<{ calle: string; factor?: number }>
      }) => {
        const trafficMap = data.traffic_map
        const incidents = data.incidents || []

        const fallback = [
          'match',
          ['get', 'class'],
          'highway',
          ROAD.highway,
          'primary',
          ROAD.primary,
          'secondary',
          ROAD.secondary,
          'tertiary',
          ROAD.tertiary,
          ROAD.local,
        ]

        const matchExpr: any[] = ['match', ['get', 'name']]
        for (const [name, factor] of Object.entries(trafficMap)) {
          if (!name) continue
          let color = '#16a34a'
          if (factor >= 100) color = '#7f1d1d'
          else if (factor >= 2.0) color = '#ef4444'
          else if (factor >= 1.6) color = '#f97316'
          else if (factor >= 1.3) color = '#eab308'
          matchExpr.push(name, color)
        }
        matchExpr.push(fallback)

        let finalColorExpr: any = matchExpr

        if (matchExpr.length < 4) {
          finalColorExpr = fallback
        }

        if (incidents.length > 0) {
          const caseExpr: any[] = ['case']
          for (const inc of incidents) {
            caseExpr.push(['in', inc.calle, ['coalesce', ['get', 'name'], '']], '#7f1d1d')
          }
          caseExpr.push(finalColorExpr)
          finalColorExpr = caseExpr
        }

        // Aplicar estilo de tráfico directo a GPU
        for (const layer of getRoadLayers()) {
          map.setPaintProperty(layer.id, 'line-color', finalColorExpr)
        }

        onDone?.()
      }
    )
    .catch(console.error)
}
