// Al terminar un turno en vivo, el resultado y la ruta del JSONL quedan bajo el banner,
// fuera de la vista. Esto baja el scroll del panel hasta la tarjeta una vez por sesión
// (event_log trae el session_id, así que cambia con cada End).
// Solo el scroll del panel: scrollIntoView también correría la página con el mapa.

import { useEffect, type RefObject } from 'react'

export function useLiveEndScroll(
  panelRef: RefObject<HTMLElement | null>,
  cardRef: RefObject<HTMLElement | null>,
  eventLog: string | undefined
) {
  useEffect(() => {
    const panel = panelRef.current
    const card = cardRef.current
    if (!eventLog || !panel || !card) return
    const fondo = card.offsetTop + card.offsetHeight - panel.clientHeight
    // Toda la tarjeta si cabe; si no, que se vea desde su título.
    panel.scrollTop = Math.min(card.offsetTop, Math.max(panel.scrollTop, fondo))
  }, [eventLog, panelRef, cardRef])
}
