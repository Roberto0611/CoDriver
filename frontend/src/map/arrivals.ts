// Marcadores de llegada (pickup/dropoff) de las dos motos: un pulso en las
// llegadas de los últimos minutos y un anillo punteado en el siguiente destino.

import * as maplibregl from 'maplibre-gl'

import type { Frame, Llegada } from '../lib/turno'

type Agente = 'greedy' | 'nuez'

const SVG_PICKUP = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2v0a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/></svg>`
const SVG_DROPOFF = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`

/**
 * Sincroniza `markers` con el minuto `t`: crea los que faltan y quita los que
 * ya no aplican. `markers` persiste entre llamadas (un ref de SimView).
 */
export function actualizarLlegadas(
  map: maplibregl.Map,
  markers: Record<string, maplibregl.Marker>,
  puntos: GeoJSON.FeatureCollection,
  t: number,
  agentes: Record<Agente, Frame[]>
) {
  const activeKeys = new Set<string>()

  const agregar = (key: string, llegada: Llegada, clase: string, agente: Agente) => {
    activeKeys.add(key)
    if (markers[key]) return
    const pt = puntos.features[llegada.punto]
    if (!pt || pt.geometry.type !== 'Point') return
    // El elemento raíz no debe tener transformaciones CSS, MapLibre lo controla.
    const el = document.createElement('div')
    const svg = llegada.tipo === 'pickup' ? SVG_PICKUP : SVG_DROPOFF
    el.innerHTML = `<div class="${clase} is-${agente}">${svg}</div>`
    markers[key] = new maplibregl.Marker({ element: el })
      .setLngLat(pt.geometry.coordinates as [number, number])
      .addTo(map)
  }

  for (const agente of ['greedy', 'nuez'] as const) {
    const frames = agentes[agente]

    // 1. Llegadas recientes (animación de pulso)
    for (let i = Math.max(0, t - 4); i <= t; i++) {
      const llegada = frames[i]?.llegada
      if (llegada) agregar(`${agente}-${i}`, llegada, 'marker-arrival', agente)
    }

    // 2. Siguiente destino (marcador estático punteado)
    const siguiente = frames.slice(t + 1).find((f) => f.llegada)?.llegada
    if (siguiente) {
      agregar(`${agente}-target-${siguiente.punto}`, siguiente, 'marker-target', agente)
    }
  }

  // Quitar los que ya no aplican
  for (const [key, marker] of Object.entries(markers)) {
    if (!activeKeys.has(key)) {
      marker.remove()
      delete markers[key]
    }
  }
}
