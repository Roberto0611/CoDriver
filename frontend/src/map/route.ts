import type { GeoJSON } from 'geojson'
import * as maplibregl from 'maplibre-gl'

export interface RouteInfo {
  from: string
  to: string
  lengthKm: number
  timeMin: number
  nodes: number
}

interface RouteFeature {
  properties: { from: string; to: string; length_km: number; time_min: number; nodes: number }
  geometry: { coordinates: [number, number][] }
}

export interface RouteGeoJSON {
  type: 'FeatureCollection'
  features: RouteFeature[]
}

const API = 'http://127.0.0.1:8000'

export async function fetchRoute(origen: string, destino: string): Promise<RouteGeoJSON> {
  const res = await fetch(`${API}/api/route?origen=${origen}&destino=${destino}`)
  if (!res.ok) throw new Error('Error fetching route')
  return res.json()
}

export function routeInfoOf(data: RouteGeoJSON): RouteInfo | null {
  const f = data.features[0]
  if (!f) return null
  const p = f.properties
  return { from: p.from, to: p.to, lengthKm: p.length_km, timeMin: p.time_min, nodes: p.nodes }
}

function marker(kind: 'origin' | 'destination', label: string) {
  const el = document.createElement('div')
  el.className = kind === 'origin' ? 'marker' : 'marker is-destination'
  const html = `<strong>${label}</strong><br><span class="muted">${
    kind === 'origin' ? 'Origin' : 'Destination'
  }</span>`
  return new maplibregl.Marker({ element: el }).setPopup(
    new maplibregl.Popup({ offset: 12 }).setHTML(html)
  )
}

/** Pinta la ruta, coloca los dos marcadores y encuadra el mapa. */
export function drawRoute(
  map: maplibregl.Map,
  data: RouteGeoJSON,
  info: RouteInfo,
  markers: { origin: maplibregl.Marker | null; destination: maplibregl.Marker | null }
) {
  const source = map.getSource('route') as maplibregl.GeoJSONSource | undefined
  source?.setData(data as unknown as GeoJSON)

  const coords = data.features[0].geometry.coordinates
  markers.origin?.remove()
  markers.destination?.remove()
  markers.origin = marker('origin', info.from).setLngLat(coords[0]).addTo(map)
  markers.destination = marker('destination', info.to)
    .setLngLat(coords[coords.length - 1])
    .addTo(map)

  const bounds = new maplibregl.LngLatBounds()
  coords.forEach((c) => bounds.extend(c))
  map.fitBounds(bounds, { padding: 50, duration: 1000 })
}
