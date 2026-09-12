import * as maplibregl from 'maplibre-gl'
import { ROAD_LAYERS } from './layers'

/** Popups al pasar el mouse por calles y zonas. Un solo popup reutilizado. */
export function attachHoverPopups(map: maplibregl.Map) {
  const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 })
  const canvas = map.getCanvas()

  const leave = () => {
    canvas.style.cursor = ''
    popup.remove()
  }

  for (const layerId of ROAD_LAYERS) {
    map.on('mouseenter', layerId, (e) => {
      const props = e.features?.[0]?.properties
      if (!props) return
      canvas.style.cursor = 'pointer'

      const name = props.name || 'Unnamed street'
      const speed = props.speed ? `${props.speed} km/h` : '—'
      const cls = props.class || 'local'

      popup
        .setLngLat(e.lngLat)
        .setHTML(
          `<strong>${name}</strong><br>` +
            `<span class="muted">Type</span> ${cls} · ` +
            `<span class="muted">Speed</span> ${speed}`
        )
        .addTo(map)
    })
    map.on('mouseleave', layerId, leave)
  }

}
