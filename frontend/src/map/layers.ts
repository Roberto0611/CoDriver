import type { GeoJSON } from 'geojson'
import type { ExpressionSpecification, GeoJSONSource, Map as MLMap } from 'maplibre-gl'
import { AMBER, PLUM, ROAD, ROUND, ROUTE_CASING, ROUTE_COLOR } from './style'
import { getRoadFeatures } from './roads'

const EMPTY = { type: 'FeatureCollection' as const, features: [] }

export const ROAD_LAYERS = [
  'roads-highway',
  'roads-primary',
  'roads-secondary',
  'roads-tertiary',
  'roads-local',
]

const zoomWidth = (...stops: number[]): ExpressionSpecification => [
  'interpolate',
  ['linear'],
  ['zoom'],
  ...stops,
]

/**
 * Capas por tipo de vía. Mapa claro: de local a autopista, cada nivel es más
 * ancho y más blanco. Las dos vías grandes llevan un borde (casing) para
 * separarse del canvas sin cambiar de color.
 */
export function addRoadLayers(map: MLMap) {
  map.addSource('road-network', { type: 'geojson', data: EMPTY })

  const road = (id: string, cls: string, color: string, width: ExpressionSpecification, minzoom?: number) => {
    const layer: any = {
      id,
      type: 'line',
      source: 'road-network',
      filter: ['==', ['get', 'class'], cls],
      paint: { 'line-color': color, 'line-width': width },
      layout: ROUND,
    }
    if (minzoom !== undefined) layer.minzoom = minzoom
    map.addLayer(layer)
  }

  // Locales/residenciales (224K features — 83% del grafo)
  map.addLayer({
    id: 'roads-local',
    type: 'line',
    source: 'road-network',
    minzoom: 13.5,
    filter: ['==', ['get', 'class'], 'local'],
    paint: {
      'line-color': ROAD.local,
      'line-width': zoomWidth(14, 0.6, 16, 1.6, 17, 3),
      'line-opacity': zoomWidth(14, 0.6, 16, 1),
    },
    layout: ROUND,
  })
  road('roads-tertiary', 'tertiary', ROAD.tertiary, zoomWidth(13, 0.8, 15, 2.2, 17, 4.5), 12.5)
  road('roads-secondary', 'secondary', ROAD.secondary, zoomWidth(11, 0.8, 13, 2.2, 17, 5.5), 11)
  road('roads-primary-casing', 'primary', ROAD.primaryCasing, zoomWidth(9, 1.6, 13, 4.4, 17, 8.4), 8)
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
    1.0, '#16a34a',  // verde — fluido
    1.3, '#eab308',  // amarillo — moderado
    1.6, '#f97316',  // naranja — pesado
    2.0, '#ef4444',  // rojo — muy pesado
    100, '#7f1d1d',  // rojo oscuro — cierre/incidente
  ] as unknown as ExpressionSpecification,
  [
    'match',
    ['get', 'class'],
    'highway', ROAD.highway,
    'primary', ROAD.primary,
    'secondary', ROAD.secondary,
    'tertiary', ROAD.tertiary,
    ROAD.local,
  ],  // fallback: color original de la calle según su clase
]

// Colores base por clase de vía (para restaurar al apagar tráfico)
const BASE_COLORS: Record<string, string> = {
  highway: ROAD.highway,
  primary: ROAD.primary,
  secondary: ROAD.secondary,
  tertiary: ROAD.tertiary,
  local: ROAD.local,
}

/**
 * Inyecta `traffic_factor` en los features del road-network que coincidan
 * con los keywords del tráfico, y cambia el paint de las capas a colores
 * térmicos. Al desactivar, restaura los colores originales.
 */
export function toggleTrafficLayer(
  map: MLMap,
  visible: boolean,
  hora?: string,
  onDone?: () => void,
) {
  if (!visible) {
    // Restaurar colores originales
    for (const layerId of ROAD_LAYERS) {
      const cls = layerId.replace('roads-', '')
      const color = BASE_COLORS[cls]
      if (color && map.getLayer(layerId)) {
        map.setPaintProperty(layerId, 'line-color', color)
      }
    }
    onDone?.()
    return
  }

  // Fetch traffic data y colorear calles reales
  fetch(`${TRAFFIC_API}/api/traffic?hora=${hora ?? '14:00'}`)
    .then((r) => r.json())
    .then((data: { traffic_map: Record<string, number>; incidents: Array<{ calle: string; factor?: number }> }) => {
      const trafficMap = data.traffic_map
      const incidents = data.incidents || []

      const fallback = [
        'match',
        ['get', 'class'],
        'highway', ROAD.highway,
        'primary', ROAD.primary,
        'secondary', ROAD.secondary,
        'tertiary', ROAD.tertiary,
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

      for (const layerId of ROAD_LAYERS) {
        if (map.getLayer(layerId)) {
          map.setPaintProperty(layerId, 'line-color', finalColorExpr)
        }
      }

      onDone?.()
    })
    .catch(console.error)
}
