// Resaltado visual de un shock en el mapa. Solo pinta: no llama al backend ni
// programa su propio fin. Quien lo usa (la vista live) lo invoca cuando el
// backend confirma el shock y corre la limpieza cuando el shock expira.
//
// Varios shocks pueden estar activos a la vez y expirar en cualquier orden, así
// que el estado vive por mapa: el color base real de cada capa, los cierres
// activos y cuántas lluvias hay. Cada limpieza quita su parte y repinta desde
// ese estado; nunca guarda como "original" un color que pintó otro shock.

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

const leerColor = (map: MLMap, id: string) => map.getPaintProperty(id, 'line-color')
const leerFondo = (map: MLMap) => map.getPaintProperty('background', 'background-color')
type ColorLinea = NonNullable<ReturnType<typeof leerColor>>
type ColorFondo = NonNullable<ReturnType<typeof leerFondo>>

interface EstadoShocks {
  /** Color sin shocks de cada capa de calle pintada. Se vacía al terminar el último cierre. */
  base: Map<string, ColorLinea>
  /** Cierres activos: una entrada por llamada, aunque dos cierren la misma calle. */
  cierres: Map<symbol, string>
  /** Pinta las capas de calle que cargan mientras hay cierres activos. */
  alCargar: (() => void) | null
  lluvias: number
  fondoBase: ColorFondo | undefined
}

const estados = new WeakMap<MLMap, EstadoShocks>()

function estadoDe(map: MLMap): EstadoShocks {
  let estado = estados.get(map)
  if (!estado) {
    estado = {
      base: new Map(),
      cierres: new Map(),
      alCargar: null,
      lluvias: 0,
      fondoBase: undefined,
    }
    estados.set(map, estado)
  }
  return estado
}

// Capas de calles de relleno (`roads-<clase>-<zona>`); el casing no se pinta.
const esCapaDeCalle = (id: string) => id.startsWith('roads-') && !id.includes('-casing')

/** Resalta el shock y devuelve la función que quita solo este shock del mapa. */
export function resaltarShock(map: MLMap | null, shock: ShockVisual): () => void {
  if (!map) return () => {}

  if (shock.zoneCenter) {
    const zoom = shock.type === 'closure' ? ZOOM_CLOSURE : ZOOM_SURGE
    map.flyTo({ center: shock.zoneCenter, zoom, duration: FLY_MS })
  }

  if (shock.type === 'closure' && shock.road) return agregarCierre(map, shock.road)
  if (shock.type === 'rain') return agregarLluvia(map)
  return () => {}
}

/** Color de una capa con los cierres activos: rojo si el nombre contiene alguna calle cerrada. */
function colorConCierres(base: ColorLinea, calles: string[]): ColorLinea {
  if (calles.length === 0) return base
  const nombre: ExpressionSpecification = ['coalesce', ['get', 'name'], '']
  return [
    'case',
    ['any', ...calles.map((c): ExpressionSpecification => ['in', c, nombre])],
    CLOSURE_RED,
    base as ExpressionSpecification,
  ]
}

const callesCerradas = (estado: EstadoShocks) => [...new Set(estado.cierres.values())]

/** Registra las capas de calle nuevas (su color actual es el base) y les pinta los cierres. */
function pintarCapasNuevas(map: MLMap, estado: EstadoShocks) {
  const calles = callesCerradas(estado)
  for (const id of map.getLayersOrder()) {
    if (!esCapaDeCalle(id) || estado.base.has(id)) continue
    const base = leerColor(map, id)
    if (base === undefined) continue
    estado.base.set(id, base)
    map.setPaintProperty(id, 'line-color', colorConCierres(base, calles))
  }
}

/** Repinta las capas registradas desde su color base con los cierres que quedan. */
function repintarCierres(map: MLMap, estado: EstadoShocks) {
  const calles = callesCerradas(estado)
  for (const [id, base] of estado.base) {
    if (map.getLayer(id)) map.setPaintProperty(id, 'line-color', colorConCierres(base, calles))
  }
}

function agregarCierre(map: MLMap, road: string): () => void {
  const estado = estadoDe(map)
  const token = Symbol(road)
  estado.cierres.set(token, road)

  repintarCierres(map, estado)
  pintarCapasNuevas(map, estado)
  if (!estado.alCargar) {
    // Las calles se cargan por zona al mover el mapa (el flyTo trae zonas nuevas).
    const alCargar = () => pintarCapasNuevas(map, estado)
    estado.alCargar = alCargar
    map.on('styledata', alCargar)
  }

  return () => {
    if (!estado.cierres.delete(token)) return // ya limpiado
    repintarCierres(map, estado)
    if (estado.cierres.size > 0) return
    if (estado.alCargar) map.off('styledata', estado.alCargar)
    estado.alCargar = null
    estado.base.clear()
  }
}

function agregarLluvia(map: MLMap): () => void {
  if (!map.getLayer('background')) return () => {}
  const estado = estadoDe(map)
  if (estado.lluvias === 0) {
    estado.fondoBase = leerFondo(map)
    map.setPaintProperty('background', 'background-color', MAP_BG_DIM)
  }
  estado.lluvias += 1

  let limpiado = false
  return () => {
    if (limpiado) return
    limpiado = true
    estado.lluvias -= 1
    if (estado.lluvias > 0) return
    if (map.getLayer('background') && estado.fondoBase !== undefined) {
      map.setPaintProperty('background', 'background-color', estado.fondoBase)
    }
    estado.fondoBase = undefined
  }
}
