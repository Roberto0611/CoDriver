// Disparo de shocks en vivo (cierre vial, lluvia): avisa al backend y lo
// refleja en el mapa durante 15 segundos.

import type { Map as MLMap } from 'maplibre-gl'

import { API_URL } from '../lib/api'
import { MTY_CENTER } from './style'

export type ShockType = 'closure' | 'rain'

export async function dispararShock(map: MLMap | null, type: ShockType) {
  try {
    const payload =
      type === 'closure'
        ? { shock_type: 'closure', zone: 2, duration_min: 40, road: 'Constitución' }
        : { shock_type: 'rain', duration_min: 45 }

    await fetch(`${API_URL}/shock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!map) return
    if (type === 'closure') {
      map.flyTo({ center: [-100.315, 25.668], zoom: 15, pitch: 45, duration: 2000 })

      const roadLayers = map
        .getStyle()
        .layers.filter((l: any) => l.id.startsWith('roads-') && !l.id.includes('-casing'))
      for (const layer of roadLayers) {
        const originalColor = map.getPaintProperty(layer.id, 'line-color')
        if (originalColor && (!Array.isArray(originalColor) || originalColor[0] !== 'case')) {
          map.setPaintProperty(layer.id, 'line-color', [
            'case',
            ['in', 'Constitución', ['coalesce', ['get', 'name'], '']],
            '#ef4444', // Red
            originalColor,
          ] as any)

          setTimeout(() => {
            if (map.getLayer(layer.id)) map.setPaintProperty(layer.id, 'line-color', originalColor)
          }, 15000)
        }
      }
    } else {
      // Lluvia
      map.flyTo({ center: MTY_CENTER, zoom: 12, pitch: 0, duration: 2000 })
      const originalBg = map.getPaintProperty('background', 'background-color')
      map.setPaintProperty('background', 'background-color', '#94a3b8') // Rainy blue-gray
      setTimeout(() => {
        if (map.getLayer('background'))
          map.setPaintProperty('background', 'background-color', originalBg)
      }, 15000)
    }
  } catch (e) {
    console.error('Error triggering shock:', e)
  }
}
