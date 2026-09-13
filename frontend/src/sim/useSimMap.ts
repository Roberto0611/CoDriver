// Mapa compartido del replay grabado y del modo live: crea el mapa, las
// calles, las estelas y las dos motos, y los mueve al minuto `t`.

import { useCallback, useEffect, useRef, type RefObject } from 'react'
import * as maplibregl from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

import { baseStyle, MTY_CENTER, MTY_ZOOM } from '../map/style'
import { createRoadLoader } from '../map/roads'
import { addTrailLayers } from '../map/trails'
import { actualizarLlegadas } from '../map/arrivals'
import { posicionEnMinuto, estelaHastaT } from '../lib/sim'
import type { TurnoData } from '../lib/turno'

maplibregl.setWorkerUrl(maplibreWorkerUrl)

const SVG_MOTO = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="17" r="3"/><circle cx="19" cy="17" r="3"/><path d="M5 14l3-7h4l3 7"/><path d="M8 7h8l3 10"/></svg>`

export function useSimMap({
  t,
  greedy,
  nuez,
  puntos,
}: {
  t: number
  greedy: TurnoData | null
  nuez: TurnoData | null
  puntos: GeoJSON.FeatureCollection | null
}): {
  mapContainer: RefObject<HTMLDivElement | null>
  mapRef: RefObject<maplibregl.Map | null>
} {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const greedyMarker = useRef<maplibregl.Marker | null>(null)
  const nuezMarker = useRef<maplibregl.Marker | null>(null)
  const arrivalMarkers = useRef<Record<string, maplibregl.Marker>>({})

  // Inicializar mapa
  const initMap = useCallback(async () => {
    if (!mapContainer.current || mapRef.current) return

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: baseStyle(),
      center: MTY_CENTER,
      zoom: MTY_ZOOM,
      pitch: 0,
      bearing: 0,
      maxZoom: 18,
      minZoom: 11,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')

    map.on('load', async () => {
      try {
        const loadNearby = createRoadLoader(map, () => {})
        await loadNearby(MTY_CENTER, 8)
        let debounceTimer: ReturnType<typeof setTimeout>
        map.on('moveend', () => {
          if (map.getZoom() < 11) return
          clearTimeout(debounceTimer)
          debounceTimer = setTimeout(() => {
            const c = map.getCenter()
            loadNearby([c.lng, c.lat], 1)
          }, 300)
        })

        addTrailLayers(map)
      } catch (err) {
        console.error('Error cargando datos del grafo:', err)
      }
    })

    // Crear marcadores
    const mkGreedy = document.createElement('div')
    mkGreedy.className = 'marker-moto is-greedy'
    mkGreedy.innerHTML = SVG_MOTO
    greedyMarker.current = new maplibregl.Marker({ element: mkGreedy })
      .setLngLat(MTY_CENTER)
      .addTo(map)

    const mkNuez = document.createElement('div')
    mkNuez.className = 'marker-moto is-nuez'
    mkNuez.innerHTML = SVG_MOTO
    nuezMarker.current = new maplibregl.Marker({ element: mkNuez }).setLngLat(MTY_CENTER).addTo(map)
  }, [])

  useEffect(() => {
    initMap()
    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [initMap])

  // Actualizar posiciones y estelas cuando cambia `t`
  useEffect(() => {
    const map = mapRef.current
    if (!map || !greedy || !nuez || !puntos) return

    const posG = posicionEnMinuto(t, greedy.tramos, greedy.geometria, greedy.config, puntos)
    const posN = posicionEnMinuto(t, nuez.tramos, nuez.geometria, nuez.config, puntos)

    greedyMarker.current?.setLngLat(posG)
    nuezMarker.current?.setLngLat(posN)

    // Actualizar estelas
    if (map.getSource('trail-greedy')) {
      const trailG = estelaHastaT(t, greedy.tramos, greedy.geometria)
      ;(map.getSource('trail-greedy') as maplibregl.GeoJSONSource).setData(trailG)
    }
    if (map.getSource('trail-nuez')) {
      const trailN = estelaHastaT(t, nuez.tramos, nuez.geometria)
      ;(map.getSource('trail-nuez') as maplibregl.GeoJSONSource).setData(trailN)
    }

    // Marcadores de llegada y siguiente destino
    actualizarLlegadas(map, arrivalMarkers.current, puntos, t, {
      greedy: greedy.frames,
      nuez: nuez.frames,
    })
  }, [t, greedy, nuez, puntos])

  return { mapContainer, mapRef }
}
