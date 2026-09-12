// Carga de datos grabados. Todo se sirve desde frontend/public/.
// Cache en memoria para evitar refetches innecesarios.

import type { TurnoData, TurnoIndex } from './turno'

let _puntosCache: GeoJSON.FeatureCollection | null = null
let _indiceCache: TurnoIndex | null = null

/** Carga los dos turnos (greedy y nuez) para un seed. */
export async function cargarTurnosPorSeed(
  seed: number
): Promise<{ greedy: TurnoData; nuez: TurnoData }> {
  const [gRes, nRes] = await Promise.all([
    fetch(`/turno_greedy_${seed}.json`),
    fetch(`/turno_nuez_${seed}.json`),
  ])

  if (!gRes.ok) throw new Error(`No se encontró turno_greedy_${seed}.json`)
  if (!nRes.ok) throw new Error(`No se encontró turno_nuez_${seed}.json`)

  const [greedy, nuez] = await Promise.all([
    gRes.json() as Promise<TurnoData>,
    nRes.json() as Promise<TurnoData>,
  ])

  return { greedy, nuez }
}

/** Carga el índice de turnos grabados. */
export async function cargarIndiceTurnos(): Promise<TurnoIndex> {
  if (_indiceCache) return _indiceCache
  const res = await fetch('/turnos.json')
  if (!res.ok) throw new Error('No se encontró turnos.json')
  _indiceCache = (await res.json()) as TurnoIndex
  return _indiceCache
}

/** Carga los 210 puntos del mapa (GeoJSON). */
export async function cargarPuntos(): Promise<GeoJSON.FeatureCollection> {
  if (_puntosCache) return _puntosCache
  const res = await fetch('/puntos.json')
  if (!res.ok) throw new Error('No se encontró puntos.json')
  _puntosCache = (await res.json()) as GeoJSON.FeatureCollection
  return _puntosCache
}
