// La voz de Nuez en /live, sacada de LiveSimView para que la vista solo diga CUÁNDO pasa
// algo (un snapshot, una pausa, un End) y aquí se decida qué suena. Qué frases y en qué orden
// sigue siendo de liveNarration.ts, que es puro y está probado; esto nomás guarda el estado
// entre ticks en refs y le pasa las frases a say()/callar().
//
// Refs y no estado: el loop de ticks lee lo que hay AHORA, no lo del render que agendó el
// setTimeout. `voz` y `fuenteVoz` sí son estado porque los pinta la píldora.

import { useEffect, useRef, useState } from 'react'

import type { Vehiculo } from '../contract'
import type { LiveSnapshot } from '../lib/live'
import { handOff, initialNarration, phrasesToSay, type ShockRef } from './liveNarration'
import { callar, onFuente, say, unlock, type FuenteVoz } from './nuez'

const narracionNueva = () => ({
  /** El shock más reciente de la sesión, con su pedido si es delay. */
  ultimoShock: null as ShockRef | null,
  /** Lo que ya se narró (liveNarration). */
  estado: initialNarration(),
  /** La sesión se terminó a mano: ya no se dice nada de ella. */
  callada: false,
  /** La última frase encolada mientras no termine; null si Nuez está en silencio. */
  hablando: null as Promise<void> | null,
  /** La reacción a un shock mientras suena: solo otra reacción la corta (handOff). */
  reaccion: null as Promise<void> | null,
})

export function useLiveNarration() {
  const [voz, setVoz] = useState(true)
  const [fuenteVoz, setFuenteVoz] = useState<FuenteVoz>('elevenlabs')
  const vozRef = useRef(true)
  const narracion = useRef(narracionNueva())

  useEffect(() => onFuente(setFuenteVoz), [])

  /** Anota el shock más reciente del snapshot. Va antes de narrar el mismo snapshot. */
  const verShocks = (snap: LiveSnapshot) => {
    const n = narracion.current
    // Empate de minuto: gana el último de la lista, que es el último inyectado.
    for (const s of snap.active_shocks) {
      if (n.ultimoShock !== null && s.starts_at_min < n.ultimoShock.minute) continue
      n.ultimoShock = { minute: s.starts_at_min, orderId: s.type === 'delay' ? s.order_id : null }
    }
  }

  // Las decisiones nuevas llegan en los frames del tick; qué decir y qué entregar lo
  // deciden phrasesToSay y handOff. Con la voz apagada se sigue llevando la cuenta del
  // shock: al encenderla no se dice tarde una reacción vieja.
  // `corriendo`: un tick que ya venía en camino cuando se pausó no habla.
  // `vehiculo`: la frase inglesa de un bloqueo duro cambia entre moto y carro (fraseVozEnVivo).
  const narrar = (snap: LiveSnapshot, corriendo: boolean, vehiculo: Vehiculo) => {
    const n = narracion.current
    const decisiones = snap.nuez.frames.flatMap((f) => f.decisiones)
    const r = phrasesToSay(decisiones, n.ultimoShock, n.estado, vehiculo)
    n.estado = r.state
    const puedeHablar = vozRef.current && !n.callada && corriendo
    if (!puedeHablar || !r.phrases.length) return
    const entrega = handOff(r.phrases, n.hablando !== null, n.estado, n.reaccion !== null)
    n.estado = entrega.state
    if (!entrega.say.length) return
    if (entrega.interrupt) callar()
    const frases = entrega.say.map((texto) => say(texto, { lang: 'en-US' }))
    const esta = frases[frases.length - 1]
    // `reaction` dice que say[0] es la reacción: se marca mientras suene esa frase.
    const reaccion = entrega.reaction ? frases[0] : null
    n.hablando = esta
    n.reaccion = reaccion
    void esta.then(() => {
      if (n.hablando === esta) n.hablando = null
    })
    void reaccion?.then(() => {
      if (n.reaccion === reaccion) n.reaccion = null
    })
  }

  /** Calla a Nuez y suelta la marca de "hablando" (las frases calladas resuelven tarde). */
  const callarVoz = () => {
    callar()
    narracion.current.hablando = null
    narracion.current.reaccion = null
  }

  /** Otra sesión: lo que Nuez tenía en cola habla de la que se suelta. */
  const reiniciar = () => {
    callar()
    narracion.current = narracionNueva()
  }

  /** End a mano: calla ya y tampoco habla un tick que venía en camino. */
  const silenciarSesion = () => {
    narracion.current.callada = true
    callarVoz()
  }

  const alternarVoz = () => {
    unlock()
    const encendida = !vozRef.current
    vozRef.current = encendida
    setVoz(encendida)
    if (!encendida) callarVoz()
  }

  return { voz, fuenteVoz, verShocks, narrar, callarVoz, reiniciar, silenciarSesion, alternarVoz }
}
