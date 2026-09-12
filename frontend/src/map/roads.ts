import type { Feature, FeatureCollection } from 'geojson'
import type { GeoJSONSource, Map as MLMap } from 'maplibre-gl'
import { isJsonResponse, nearestZones, zonaCentrosFromGeoJSON, type LngLat } from '../lib/zones'

/** Features de la red vial cargados hasta ahora. Accesible para otros módulos (tráfico). */
let _roadFeatures: Feature[] = []
export function getRoadFeatures(): Feature[] {
  return _roadFeatures
}

/**
 * Carga perezosa de calles por zona. Los archivos `mty_edges_<zona>.json`
 * son grandes y no van al repo; se traen las zonas cercanas al centro del
 * mapa conforme el usuario se mueve.
 */
export function createRoadLoader(map: MLMap, onCount: (edges: number) => void) {
  const loaded = new Set<string>()
  let busy = false

  return async function loadNearby(center: LngLat, count: number) {
    if (busy) return
    busy = true
    try {
      const zonas = zonaCentrosFromGeoJSON(await (await fetch('/zonas.json')).json())
      let added = false

      for (const zona of nearestZones(zonas, center, loaded, count)) {
        loaded.add(zona)
        const res = await fetch(`/mty_edges_${zona}.json`)
        if (!isJsonResponse(res)) continue
        const data = (await res.json()) as FeatureCollection
        _roadFeatures = _roadFeatures.concat(data.features)
        added = true
      }

      const source = map.getSource('road-network') as GeoJSONSource | undefined
      if (added && source) {
        source.setData({ type: 'FeatureCollection', features: _roadFeatures })
        onCount(_roadFeatures.length)
      }
    } catch (e) {
      console.error('Error lazy loading', e)
    } finally {
      busy = false
    }
  }
}
