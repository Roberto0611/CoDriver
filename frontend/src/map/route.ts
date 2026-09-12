import type { GeoJSON } from 'geojson'
import * as maplibregl from 'maplibre-gl'

export interface RouteInfo {
  agent: string
  from: string
  to: string
  lengthKm: number
  timeMin: number
  nodes: number
}

export interface VSInfo {
  classic: RouteInfo | null
  ai: RouteInfo | null
}

interface RouteFeature {
  properties: RouteInfo
  geometry: { coordinates: [number, number][] }
}

export interface RouteGeoJSON {
  type: 'FeatureCollection'
  features: RouteFeature[]
}

const API = 'http://127.0.0.1:8000'

export async function fetchRoute(
  origen: string,
  destino: string,
  hora?: string
): Promise<RouteGeoJSON> {
  let url = `${API}/api/route?origen=${origen}&destino=${destino}`
  if (hora) url += `&hora=${hora}`
  const res = await fetch(url)
  if (!res.ok) throw new Error('Error fetching route')
  return res.json()
}

export function routeInfoOf(data: RouteGeoJSON): VSInfo {
  const classicFeature = data.features.find(f => f.properties.agent === 'classic')
  const aiFeature = data.features.find(f => f.properties.agent === 'ai')

  const toInfo = (f: RouteFeature | undefined): RouteInfo | null => {
    if (!f) return null
    return {
      agent: f.properties.agent,
      from: f.properties.from,
      to: f.properties.to,
      lengthKm: f.properties.length_km || f.properties.lengthKm,
      timeMin: f.properties.time_min || f.properties.timeMin,
      nodes: f.properties.nodes
    }
  }

  return {
    classic: toInfo(classicFeature),
    ai: toInfo(aiFeature)
  }
}

function marker(kind: 'origin' | 'destination' | 'classic' | 'ai', label: string) {
  const el = document.createElement('div')
  if (kind === 'origin') {
    el.className = 'marker'
  } else if (kind === 'destination') {
    el.className = 'marker is-destination'
  } else if (kind === 'classic') {
    el.className = 'marker is-classic-car'
    el.innerHTML = '🤖' // Classic Agent
  } else if (kind === 'ai') {
    el.className = 'marker is-ai-car'
    el.innerHTML = '🧠' // AI Agent
  }

  return new maplibregl.Marker({ element: el }).setPopup(
    new maplibregl.Popup({ offset: 12 }).setHTML(`<strong>${label}</strong>`)
  )
}

/** Pinta las rutas, coloca marcadores y encuadra el mapa. */
export function drawRoute(
  map: maplibregl.Map,
  data: RouteGeoJSON,
  info: VSInfo,
  markers: { origin: maplibregl.Marker | null; destination: maplibregl.Marker | null; classicCar: maplibregl.Marker | null; aiCar: maplibregl.Marker | null }
) {
  const source = map.getSource('route') as maplibregl.GeoJSONSource | undefined
  source?.setData(data as unknown as GeoJSON)

  markers.origin?.remove()
  markers.destination?.remove()
  markers.classicCar?.remove()
  markers.aiCar?.remove()

  const bounds = new maplibregl.LngLatBounds()

  const classicFeature = data.features.find(f => f.properties.agent === 'classic')
  const aiFeature = data.features.find(f => f.properties.agent === 'ai')

  if (classicFeature && info.classic) {
    const coords = classicFeature.geometry.coordinates
    markers.origin = marker('origin', info.classic.from).setLngLat(coords[0]).addTo(map)
    markers.destination = marker('destination', info.classic.to).setLngLat(coords[coords.length - 1]).addTo(map)
    // Place classic car somewhere on the route or at origin
    markers.classicCar = marker('classic', 'Agente Clásico').setLngLat(coords[0]).addTo(map)
    coords.forEach((c) => bounds.extend(c))
  }

  if (aiFeature && info.ai) {
    const coords = aiFeature.geometry.coordinates
    // Place AI car
    markers.aiCar = marker('ai', 'Nuez IA').setLngLat(coords[0]).addTo(map)
    coords.forEach((c) => bounds.extend(c))
  }

  if (!bounds.isEmpty()) {
    map.fitBounds(bounds, { padding: 50, duration: 1000 })
  }
}
