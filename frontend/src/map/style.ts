import type { StyleSpecification } from 'maplibre-gl'

// Centro de Monterrey
export const MTY_CENTER: [number, number] = [-100.3161, 25.6866]
export const MTY_ZOOM = 14

// Paleta del mapa (ver docs/ui-style-guide.md). MapLibre no lee variables
// CSS, así que los hex viven aquí. Un mapa claro: calles blancas sobre canvas
// cálido, la ruta en índigo porque índigo = decisión del algoritmo.
export const MAP_BG = '#EFEAE6'
export const ROUTE_COLOR = '#4F46E5'
export const ROUTE_CASING = '#FFFFFF'
export const PLUM = '#684959'
export const AMBER = '#F59E0B'
// Shocks (map/shocks.ts): calle cerrada en rojo; la lluvia oscurece el fondo al tono --hairline.
export const CLOSURE_RED = '#EF4444'
export const MAP_BG_DIM = '#D8CCCA'

export const ROAD = {
  highway: '#F3DFA2',
  highwayCasing: '#E2C97E',
  primary: '#FFFFFF',
  primaryCasing: '#D8CCCA',
  secondary: '#FFFFFF',
  tertiary: '#FBF8F6',
  local: '#F7F3F0',
}

export const ROUND = { 'line-cap': 'round' as const, 'line-join': 'round' as const }

/** Estilo base: solo el fondo. Las capas se agregan al cargar. */
export function baseStyle(): StyleSpecification {
  return {
    version: 8,
    name: 'MTY Light',
    sources: {},
    layers: [{ id: 'background', type: 'background', paint: { 'background-color': MAP_BG } }],
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
  }
}
