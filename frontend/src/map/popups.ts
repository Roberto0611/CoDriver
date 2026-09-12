import * as maplibregl from 'maplibre-gl'

/** Popups al pasar el mouse por calles. Un solo popup reutilizado. */
export function attachHoverPopups(map: maplibregl.Map) {
  const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 })
  const canvas = map.getCanvas()

  const leave = () => {
    canvas.style.cursor = ''
    popup.remove()
  }

  map.on('mousemove', (e) => {
    const features = map.queryRenderedFeatures(e.point)
    const road = features.find(
      (f) => f.layer.id.startsWith('roads-') && !f.layer.id.includes('-casing')
    )

    if (!road) {
      if (popup.isOpen()) leave()
      return
    }

    const props = road.properties
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

  map.on('mouseout', leave)
}
