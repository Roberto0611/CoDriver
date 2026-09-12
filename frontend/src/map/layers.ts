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
