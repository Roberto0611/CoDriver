// Lo que /live necesita del backend y de public/ antes de arrancar un turno: los puntos del
// mapa, las zonas para el ancla y el seed ensayado. Se carga una vez al montar y otra vez
// con `recargar` (el Retry del error de catálogo).

import { useEffect, useState } from 'react'

import { getRehearsal, getZones, type LiveRehearsal, type LiveZone } from '../lib/live'
import { cargarPuntos } from '../lib/loader'

const mensaje = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useLiveCatalog(onError: (message: string) => void) {
  const [puntos, setPuntos] = useState<GeoJSON.FeatureCollection | null>(null)
  const [zones, setZones] = useState<LiveZone[]>([])
  const [rehearsal, setRehearsal] = useState<LiveRehearsal | null>(null)

  const recargar = () => {
    cargarPuntos()
      .then(setPuntos)
      .catch(() => onError("Couldn't load the map points (puntos.json)"))
    getZones()
      .then(setZones)
      .catch((e) => onError(mensaje(e)))
    getRehearsal()
      .then(setRehearsal)
      .catch((e) => onError(mensaje(e)))
  }

  useEffect(() => {
    recargar()
  }, [])

  return { puntos, zones, rehearsal, recargar }
}
