// Aviso de una decisión de Nuez: pedido bloqueado (rosa) o aceptado (esmeralda).
// Aparece abajo a la derecha con un rebote y se queda al menos VISIBLE_MS,
// aunque la simulación ya haya pasado de minuto. Los bloqueos llegan cada 1-3
// minutos simulados (<1 s a ×1): si el aviso ya está visible, uno nuevo cambia
// el texto, reinicia el conteo y repite solo la parte del sobrepaso.
// Sale con la misma animación al revés, sola o con la X.

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Icon } from '../ui/icons'

const VISIBLE_MS = 3000
const SALIDA_MS = 520 // igual que toast-pop-out en toast.css

// Solo el sobrepaso de toast-pop: 1 → 1.08 → 0.98 → 1.
const SOBREPASO: Keyframe[] = [
  { transform: 'scale(1)' },
  { transform: 'scale(1.08)', offset: 0.4 },
  { transform: 'scale(0.98)', offset: 0.75 },
  { transform: 'scale(1)' },
]

const VARIANTES = {
  blocked: { titulo: 'Offer blocked', icono: Icon.shield },
  accepted: { titulo: 'Order accepted', icono: Icon.accept },
} as const

interface Aviso {
  /** Cambia solo cuando el aviso entra desde oculto: remonta y rebota completo. */
  aparicion: number
  /** Cambia con cada decisión mientras está visible: sobrepaso y conteo nuevo. */
  actualizacion: number
  texto: string
}

interface Props {
  variant: keyof typeof VARIANTES
  /** Texto de la decisión del minuto actual, o null si no hubo. */
  texto: string | null
  /** Identifica la decisión: seed + minuto + oferta. */
  decisionKey: string | null
}

export function DecisionToast({ variant, texto, decisionKey }: Props) {
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const [saliendo, setSaliendo] = useState(false)
  const [ultimaKey, setUltimaKey] = useState<string | null>(null)
  const tarjeta = useRef<HTMLDivElement>(null)
  const { titulo, icono } = VARIANTES[variant]

  // Ajuste de estado durante el render (patrón de React) cuando llega otra decisión.
  if (decisionKey !== ultimaKey) {
    setUltimaKey(decisionKey)
    if (texto && decisionKey) {
      setAviso(
        aviso && !saliendo
          ? { ...aviso, actualizacion: aviso.actualizacion + 1, texto }
          : { aparicion: (aviso?.aparicion ?? 0) + 1, actualizacion: 0, texto }
      )
      setSaliendo(false)
    }
  }

  // Conteo de salida: se reinicia con cada decisión nueva (aviso cambia de identidad).
  useEffect(() => {
    if (!aviso) return
    if (saliendo) {
      const id = setTimeout(() => setAviso(null), SALIDA_MS)
      return () => clearTimeout(id)
    }
    const id = setTimeout(() => setSaliendo(true), VISIBLE_MS)
    return () => clearTimeout(id)
  }, [aviso, saliendo])

  // Sobrepaso al cambiar el texto. Web Animations para no remontar la tarjeta
  // (conserva el foco de la X) y porque tapa a la animación CSS mientras corre.
  const actualizacion = aviso?.actualizacion ?? 0
  useLayoutEffect(() => {
    const el = tarjeta.current
    if (!el || actualizacion === 0 || saliendo) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const animacion = el.animate(SOBREPASO, {
      duration: 380,
      easing: 'cubic-bezier(0.3, 0.7, 0.4, 1)',
    })
    // Al empezar la salida se cancela, para no tapar toast-pop-out.
    return () => animacion.cancel()
  }, [actualizacion, saliendo])

  return (
    <div role="status" aria-live="polite">
      {aviso && (
        <div
          key={aviso.aparicion}
          ref={tarjeta}
          className={`decision-toast is-${variant} ${saliendo ? 'is-leaving' : ''}`}
        >
          <span className="decision-toast-icon">{icono}</span>
          <div className="decision-toast-body">
            <span className="caps">{titulo}</span>
            <span className="decision-toast-label">{aviso.texto}</span>
          </div>
          <button
            type="button"
            className="decision-toast-close"
            aria-label="Dismiss notification"
            disabled={saliendo}
            onClick={() => setSaliendo(true)}
          >
            {Icon.skip}
          </button>
        </div>
      )}
    </div>
  )
}
