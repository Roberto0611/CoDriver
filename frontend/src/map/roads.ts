import type { FeatureCollection } from 'geojson'
import type { Map as MLMap } from 'maplibre-gl'
import { isJsonResponse, nearestZones, zonaCentrosFromGeoJSON, type LngLat } from '../lib/zones'

import { addRoadLayers } from './layers'

/**
 * Carga perezosa de calles por zona. Los archivos `mty_edges_<zona>.json`
 * son grandes y no van al repo; se traen las zonas cercanas al centro del
 * mapa conforme el usuario se mueve.
 */
export function createRoadLoader(map: MLMap, onCount: (edges: number) => void) {
  const loaded = new Set<string>()
  let busy = false
  let totalEdges = 0

  return async function loadNearby(center: LngLat, count: number) {
    if (busy) return
    busy = true
    try {
      const zonas = zonaCentrosFromGeoJSON(await (await fetch('/zonas.json')).json())

      for (const zona of nearestZones(zonas, center, loaded, count)) {
        loaded.add(zona)
        const res = await fetch(`/mty_edges_${zona}.json`)
        if (!isJsonResponse(res)) continue
        const data = (await res.json()) as FeatureCollection

        // Agregar fuente y capas exclusivas para esta zona de forma independiente
        addRoadLayers(map, zona, data)

        totalEdges += data.features.length
        onCount(totalEdges)
      }
    } catch (e) {
      console.error('Error lazy loading', e)
    } finally {
      busy = false
    }
  }
}
