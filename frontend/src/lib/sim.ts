// Motor de simulación: funciones puras para interpolar posición de la moto,
// convertir minutos a hora, y calcular contadores acumulados.
// Cada función es testeable sin DOM ni mapa.

import type { Tramo, Frame } from './turno'
import type { ConfigTurno } from '../contract'

// ── Geometría ────────────────────────────────────────────────────────────

/** Distancia euclidiana entre dos coordenadas [lon, lat] en grados.
 *  Suficiente para interpolar a escala de ciudad (error < 0.1%). */
function dist(a: [number, number], b: [number, number]): number {
  const dx = a[0] - b[0]
  const dy = a[1] - b[1]
  return Math.sqrt(dx * dx + dy * dy)
}

/** Distancias parciales acumuladas a lo largo de una polilínea.
 *  Devuelve un array del mismo largo que `coords` donde el primer
 *  elemento es 0 y el último es la longitud total. */
export function distanciaAcumulada(coords: [number, number][]): number[] {
  const d: number[] = [0]
  for (let i = 1; i < coords.length; i++) {
    d.push(d[i - 1] + dist(coords[i - 1], coords[i]))
  }
  return d
}

/** Interpola por distancia acumulada sobre una polilínea.
 *  `frac` va de 0 (inicio) a 1 (fin). */
export function interpolarSobreLinea(
  coords: [number, number][],
  frac: number
): [number, number] {
  if (coords.length === 0) return [0, 0]
  if (coords.length === 1 || frac <= 0) return coords[0]
  if (frac >= 1) return coords[coords.length - 1]

  const acum = distanciaAcumulada(coords)
  const total = acum[acum.length - 1]
  if (total === 0) return coords[0]

  const objetivo = frac * total

  // Buscar el segmento que contiene el objetivo
  for (let i = 1; i < acum.length; i++) {
    if (acum[i] >= objetivo) {
      const segLen = acum[i] - acum[i - 1]
      if (segLen === 0) return coords[i]
      const segFrac = (objetivo - acum[i - 1]) / segLen
      return [
        coords[i - 1][0] + segFrac * (coords[i][0] - coords[i - 1][0]),
        coords[i - 1][1] + segFrac * (coords[i][1] - coords[i - 1][1]),
      ]
    }
  }

  return coords[coords.length - 1]
}

// ── Posición de la moto ──────────────────────────────────────────────────

/** Coordenadas [lon, lat] de un punto del mapa por índice.
 *  `puntos` es el GeoJSON de puntos.json (FeatureCollection). */
export function coordsDePunto(
  puntos: GeoJSON.FeatureCollection,
  idx: number
): [number, number] {
  const f = puntos.features[idx]
  if (!f) return [0, 0]
  const c = (f.geometry as GeoJSON.Point).coordinates
  return [c[0], c[1]]
}

/** Posición de la moto en el minuto `t`.
 *
 *  Reglas (de front-turno-grabado.md):
 *  1. Buscar tramo con `t_salida <= t < t_llegada`, interpolar por
 *     distancia acumulada sobre geometria[clave].
 *  2. Si no hay tramo activo, la moto está en el `hasta` del último
 *     tramo terminado (coords de puntos.json).
 *  3. Antes del primer tramo, está en config.ancla. */
export function posicionEnMinuto(
  t: number,
  tramos: Tramo[],
  geometria: Record<string, [number, number][]>,
  config: ConfigTurno,
  puntos: GeoJSON.FeatureCollection
): [number, number] {
  // Buscar tramo activo
  for (const tramo of tramos) {
    if (t >= tramo.t_salida && t < tramo.t_llegada) {
      const coords = geometria[tramo.clave]
      if (!coords || coords.length === 0) {
        return coordsDePunto(puntos, tramo.desde)
      }
      const frac = (t - tramo.t_salida) / (tramo.t_llegada - tramo.t_salida)
      return interpolarSobreLinea(coords, frac)
    }
  }

  // Sin tramo activo: buscar el último tramo terminado
  let ultimoTerminado: Tramo | null = null
  for (const tramo of tramos) {
    if (tramo.t_llegada <= t) {
      ultimoTerminado = tramo
    }
  }

  if (ultimoTerminado) {
    return coordsDePunto(puntos, ultimoTerminado.hasta)
  }

  // Antes del primer tramo: ancla
  return [config.ancla.lon, config.ancla.lat]
}

// ── Tiempo ───────────────────────────────────────────────────────────────

/** Convierte (hora_inicio, minuto_t) a "HH:MM".
 *  Ej: minutosAHora(14, 25) → "14:25". */
export function minutosAHora(horaInicio: number, t: number): string {
  const totalMin = horaInicio * 60 + t
  const h = Math.floor(totalMin / 60)
    .toString()
    .padStart(2, '0')
  const m = (totalMin % 60).toString().padStart(2, '0')
  return `${h}:${m}`
}

// ── Contadores ───────────────────────────────────────────────────────────

export interface Contadores {
  ganado: number
  entregas: number
  saltadas: number
}

/** Contadores acumulados hasta el minuto `t` (inclusive). */
export function contadoresEnT(frames: Frame[], t: number): Contadores {
  let entregas = 0
  let saltadas = 0
  let ganado = 0

  for (let i = 0; i <= Math.min(t, frames.length - 1); i++) {
    const f = frames[i]
    if (f.cobro > 0) entregas++
    for (const d of f.decisiones) {
      if (d.accion === 'saltar') saltadas++
    }
    ganado = f.ganado // el campo ya es acumulado
  }

  return { ganado, entregas, saltadas }
}

// ── Estela de ruta recorrida ─────────────────────────────────────────────

/** Genera un GeoJSON LineString con la ruta recorrida hasta el minuto `t`. */
export function estelaHastaT(
  t: number,
  tramos: Tramo[],
  geometria: Record<string, [number, number][]>
): GeoJSON.Feature<GeoJSON.MultiLineString> {
  const lines: [number, number][][] = []

  for (const tramo of tramos) {
    const coords = geometria[tramo.clave]
    if (!coords || coords.length === 0) continue

    if (tramo.t_llegada <= t) {
      // Tramo completo
      lines.push(coords)
    } else if (tramo.t_salida <= t) {
      // Tramo parcial: cortar hasta la posición actual
      const frac = (t - tramo.t_salida) / (tramo.t_llegada - tramo.t_salida)
      const acum = distanciaAcumulada(coords)
      const total = acum[acum.length - 1]
      const objetivo = frac * total

      const parcial: [number, number][] = [coords[0]]
      for (let i = 1; i < coords.length; i++) {
        if (acum[i] >= objetivo) {
          // Interpolar el último punto
          const segLen = acum[i] - acum[i - 1]
          const segFrac = segLen === 0 ? 0 : (objetivo - acum[i - 1]) / segLen
          parcial.push([
            coords[i - 1][0] + segFrac * (coords[i][0] - coords[i - 1][0]),
            coords[i - 1][1] + segFrac * (coords[i][1] - coords[i - 1][1]),
          ])
          break
        }
        parcial.push(coords[i])
      }
      lines.push(parcial)
    }
    // Si t < t_salida, no se agrega nada
  }

  return {
    type: 'Feature',
    properties: {},
    geometry: { type: 'MultiLineString', coordinates: lines },
  }
}
