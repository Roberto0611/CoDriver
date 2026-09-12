import type { GeoJSON } from 'geojson'
import type { ExpressionSpecification, Map as MLMap } from 'maplibre-gl'
import { AMBER, PLUM, ROAD, ROUND, ROUTE_CASING, ROUTE_COLOR } from './style'

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

  const road = (id: string, cls: string, color: string, width: ExpressionSpecification) =>
    map.addLayer({
      id,
      type: 'line',
      source: 'road-network',
      filter: ['==', ['get', 'class'], cls],
      paint: { 'line-color': color, 'line-width': width },
      layout: ROUND,
    })

  // Locales/residenciales (224K features — 83% del grafo)
  map.addLayer({
    id: 'roads-local',
    type: 'line',
    source: 'road-network',
    filter: ['==', ['get', 'class'], 'local'],
    paint: {
      'line-color': ROAD.local,
      'line-width': zoomWidth(14, 0.6, 16, 1.6, 17, 3),
      'line-opacity': zoomWidth(14, 0.6, 16, 1),
    },
    layout: ROUND,
  })
  road('roads-tertiary', 'tertiary', ROAD.tertiary, zoomWidth(13, 0.8, 15, 2.2, 17, 4.5))
  road('roads-secondary', 'secondary', ROAD.secondary, zoomWidth(11, 0.8, 13, 2.2, 17, 5.5))
  road('roads-primary-casing', 'primary', ROAD.primaryCasing, zoomWidth(9, 1.6, 13, 4.4, 17, 8.4))
  road('roads-primary', 'primary', ROAD.primary, zoomWidth(9, 1, 13, 3, 17, 6.4))
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

/**
 * Zonas. El color significa algo: ciruela = zona normal, ámbar = riesgosa de
 * noche. Un solo tono, no catorce. Van arriba de las calles para no perder
 * el hover.
 */
export function addZonaLayers(map: MLMap, data: GeoJSON) {
  const blocked: ExpressionSpecification = ['==', ['get', 'bloqueada_noche'], true]
  const color: ExpressionSpecification = ['case', blocked, AMBER, PLUM]

  map.addSource('zonas', { type: 'geojson', data })
  map.addLayer({
    id: 'zonas-fill',
    type: 'fill',
    source: 'zonas',
    paint: { 'fill-color': color, 'fill-opacity': ['case', blocked, 0.1, 0.05] },
  })
  map.addLayer({
    id: 'zonas-line',
    type: 'line',
    source: 'zonas',
    paint: {
      'line-color': color,
      'line-width': 1.5,
      'line-opacity': 0.45,
      'line-dasharray': [3, 3],
    },
  })
}

/** Los 210 puntos de interés del simulador: puntos discretos en ciruela. */
export function addPuntosLayer(map: MLMap, data: GeoJSON) {
  map.addSource('puntos', { type: 'geojson', data })
  map.addLayer({
    id: 'puntos-circle',
    type: 'circle',
    source: 'puntos',
    paint: {
      'circle-color': PLUM,
      'circle-radius': zoomWidth(10, 1.5, 14, 3),
      'circle-opacity': 0.55,
      'circle-stroke-width': 1,
      'circle-stroke-color': '#FFFFFF',
    },
  })
}

// ── Tráfico ──────────────────────────────────────────────────────────────

const TRAFFIC_API = 'http://127.0.0.1:8000'

/** Agrega las capas de tráfico (ocultas por defecto). */
export function addTrafficLayers(map: MLMap) {
  map.addSource('traffic', { type: 'geojson', data: EMPTY })

  map.addLayer({
    id: 'traffic-glow',
    type: 'line',
    source: 'traffic',
    filter: ['==', ['get', 'tipo'], 'TRAFICO'],
    paint: {
      'line-color': [
        'interpolate',
        ['linear'],
        ['get', 'factor_retraso'],
        1.0, '#16a34a',
        1.3, '#eab308',
        1.8, '#f97316',
        3.0, '#ef4444',
      ] as unknown as string,
      'line-width': zoomWidth(9, 10, 14, 30),
      'line-blur': zoomWidth(9, 6, 14, 18),
      'line-opacity': 0.4,
    },
    layout: { ...ROUND, visibility: 'none' },
  })

  map.addLayer({
    id: 'traffic-incident',
    type: 'line',
    source: 'traffic',
    filter: ['==', ['get', 'tipo'], 'CIERRE_TOTAL'],
    paint: {
      'line-color': '#dc2626',
      'line-width': zoomWidth(9, 6, 14, 16),
      'line-blur': zoomWidth(9, 3, 14, 8),
      'line-opacity': 0.75,
    },
    layout: { ...ROUND, visibility: 'none' },
  })
}

/** Activa o desactiva las capas de tráfico y carga datos para la hora dada. */
export function toggleTrafficLayer(map: MLMap, visible: boolean, hora?: string) {
  const vis = visible ? 'visible' : 'none'
  if (map.getLayer('traffic-glow')) map.setLayoutProperty('traffic-glow', 'visibility', vis)
  if (map.getLayer('traffic-incident')) map.setLayoutProperty('traffic-incident', 'visibility', vis)

  if (visible && hora) {
    fetch(`${TRAFFIC_API}/api/traffic?hora=${hora}`)
      .then((r) => r.json())
      .then((data) => {
        const source = map.getSource('traffic') as import('maplibre-gl').GeoJSONSource | undefined
        source?.setData(data.geojson)
      })
      .catch(console.error)
  }
}
