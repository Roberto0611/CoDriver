// Resaltado visual de un shock en el mapa. Solo pinta: no llama al backend ni
// programa su propio fin. Quien lo usa (la vista live) lo invoca cuando el
// backend confirma el shock y corre la limpieza cuando el shock expira.

import type { ExpressionSpecification, Map as MLMap } from 'maplibre-gl'

import { CLOSURE_RED, MAP_BG_DIM } from './style'

export interface ShockVisual {
  type: 'closure' | 'surge' | 'rain'
  /** Centro de la zona afectada, `[lon, lat]`. */
  zoneCenter?: [number, number]
  /** Nombre (o parte del nombre) de la calle cerrada. */
  road?: string
}

const ZOOM_CLOSURE = 15
const ZOOM_SURGE = 14
const FLY_MS = 2000

// Capas de calles de relleno (`roads-<clase>-<zona>`); el casing no se pinta.
const esCapaDeCalle = (id: string) => id.startsWith('roads-') && !id.includes('-casing')

/** Resalta el shock y devuelve la función que deja el mapa como estaba. */
export function resaltarShock(map: MLMap | null, shock: ShockVisual): () => void {
  if (!map) return () => {}

  if (shock.zoneCenter) {
    const zoom = shock.type === 'closure' ? ZOOM_CLOSURE : ZOOM_SURGE
    map.flyTo({ center: shock.zoneCenter, zoom, duration: FLY_MS })
  }

  if (shock.type === 'closure' && shock.road) return pintarCierre(map, shock.road)
  if (shock.type === 'rain') return oscurecerFondo(map)
  return () => {}
}

/** Pinta de rojo las calles cuyo nombre contiene `road`, incluidas las que carguen después. */
function pintarCierre(map: MLMap, road: string): () => void {
  const leerColor = (id: string) => map.getPaintProperty(id, 'line-color')
  const originales = new Map<string, NonNullable<ReturnType<typeof leerColor>>>()

  const pintar = () => {
    for (const id of map.getLayersOrder()) {
      if (!esCapaDeCalle(id) || originales.has(id)) continue
      const original = leerColor(id)
      if (original === undefined) continue
      originales.set(id, original)
      const expr: ExpressionSpecification = [
        'case',
        ['in', road, ['coalesce', ['get', 'name'], '']],
        CLOSURE_RED,
        original as ExpressionSpecification,
      ]
      map.setPaintProperty(id, 'line-color', expr)
    }
  }

  pintar()
  // Las calles se cargan por zona al mover el mapa (el flyTo trae zonas nuevas).
  map.on('styledata', pintar)

  return () => {
    map.off('styledata', pintar)
    for (const [id, original] of originales) {
      if (map.getLayer(id)) map.setPaintProperty(id, 'line-color', original)
    }
  }
}

function oscurecerFondo(map: MLMap): () => void {
  if (!map.getLayer('background')) return () => {}
  const original = map.getPaintProperty('background', 'background-color')
  map.setPaintProperty('background', 'background-color', MAP_BG_DIM)
  return () => {
    if (map.getLayer('background')) {
      map.setPaintProperty('background', 'background-color', original)
    }
  }
}
