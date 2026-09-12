// Estelas de las dos motos: fuentes vacías y capas, que SimView rellena con
// `estelaHastaT` en cada minuto.

import type { Map as MLMap } from 'maplibre-gl'

// Colores de las estelas (constantes de mapa, MapLibre no lee CSS vars)
const GREEDY_TRAIL = '#F59E0B' // ámbar
const NUEZ_TRAIL = '#4F46E5' // índigo

export function addTrailLayers(map: MLMap) {
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
      'line-offset': -2,
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
      'line-offset': 2,
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
      'line-offset': 2,
    },
    layout: { 'line-cap': 'round', 'line-join': 'round' },
  })
}
