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
  oracle: RouteInfo | null
}

interface RouteProperties {
  agent: string
  from: string
  to: string
  length_km: number
  time_min: number
  nodes: number
}

interface RouteFeature {
  properties: RouteProperties
  geometry: { coordinates: [number, number][] }
}

export interface RouteGeoJSON {
  type: 'FeatureCollection'
  features: RouteFeature[]
}

import { API_URL } from '../lib/api'
const API = API_URL

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
  const classicFeature = data.features.find((f) => f.properties.agent === 'classic')
  const aiFeature = data.features.find((f) => f.properties.agent === 'ai')
  const oracleFeature = data.features.find((f) => f.properties.agent === 'oracle')

  const toInfo = (f: RouteFeature | undefined): RouteInfo | null => {
    if (!f) return null
    return {
      agent: f.properties.agent,
      from: f.properties.from,
      to: f.properties.to,
      lengthKm: f.properties.length_km,
      timeMin: f.properties.time_min,
      nodes: f.properties.nodes,
    }
  }

  return {
    classic: toInfo(classicFeature),
    ai: toInfo(aiFeature),
    oracle: toInfo(oracleFeature),
  }
}

function marker(kind: 'origin' | 'destination' | 'classic' | 'ai' | 'oracle', label: string) {
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
  } else if (kind === 'oracle') {
    el.className = 'marker is-oracle-car'
    el.innerHTML = '👁️' // Oracle Agent
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
  markers: {
    origin: maplibregl.Marker | null
    destination: maplibregl.Marker | null
    classicCar: maplibregl.Marker | null
    aiCar: maplibregl.Marker | null
    oracleCar?: maplibregl.Marker | null
  }
) {
  const source = map.getSource('route') as maplibregl.GeoJSONSource | undefined
  source?.setData(data as unknown as GeoJSON)

  markers.origin?.remove()
  markers.destination?.remove()
  markers.classicCar?.remove()
  markers.aiCar?.remove()
  if (markers.oracleCar) markers.oracleCar.remove()

  const bounds = new maplibregl.LngLatBounds()

  const classicFeature = data.features.find((f) => f.properties.agent === 'classic')
  const aiFeature = data.features.find((f) => f.properties.agent === 'ai')
  const oracleFeature = data.features.find((f) => f.properties.agent === 'oracle')

  if (classicFeature && info.classic) {
    const coords = classicFeature.geometry.coordinates
    markers.origin = marker('origin', info.classic.from).setLngLat(coords[0]).addTo(map)
    markers.destination = marker('destination', info.classic.to)
      .setLngLat(coords[coords.length - 1])
      .addTo(map)
    // Place classic car
    markers.classicCar = marker('classic', 'Agente Clásico').setLngLat(coords[0]).addTo(map)
    coords.forEach((c) => bounds.extend(c))
  }

  if (aiFeature && info.ai) {
    const coords = aiFeature.geometry.coordinates
    // Place AI car
    markers.aiCar = marker('ai', 'Nuez IA').setLngLat(coords[0]).addTo(map)
    coords.forEach((c) => bounds.extend(c))
  }

  if (oracleFeature && info.oracle) {
    const coords = oracleFeature.geometry.coordinates
    // Place Oracle car
    markers.oracleCar = marker('oracle', 'Oráculo').setLngLat(coords[0]).addTo(map)
    coords.forEach((c) => bounds.extend(c))
  }

  if (!bounds.isEmpty()) {
    map.fitBounds(bounds, { padding: 50, duration: 1000 })
  }
}
