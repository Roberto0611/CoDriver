// Qué dice Nuez en voz alta en el turno en vivo. A diferencia del replay (frases.ts), aquí
// no se sabe de antemano qué va a pasar: no hay prefetch y se dice la `razon` tal cual,
// en español, con la voz de ElevenLabs configurada para eso.
//
// Se dicen dos cosas:
// - la reacción de Nuez a un shock, una vez por shock, aunque sea un aceptar o un salto por
//   dinero. En cierre, surge y lluvia es la primera decisión desde `starts_at_min`. En un delay
//   es la decisión sobre el pedido atrasado (`order_id`): la primera después puede ser de otro
//   pedido que no tiene nada que ver;
// - los bloqueos por seguridad, salvo que esa misma frase ya haya sonado en los últimos
//   SILENCIO_REPETIDA_MIN minutos (la misma regla que /sim). "La misma" compara la frase con
//   los números cambiados por # (claveFrase): "Llevas 90 min" y "Llevas 93 min" son la misma.
//   Hay turnos con un bloqueo casi cada minuto, y todos dicen lo mismo.
// Lo demás (aceptar de rutina, saltos por dinero) taparía lo importante.
//
// Tres niveles: la reacción al shock, la primera vez que suena cada restricción y lo normal.
// Con Nuez callada se entrega todo (a lo más MAX_FRASES_POR_TICK, en ese orden). Hablando, las
// normales se sueltan y las otras dos interrumpen; si lo que suena es una reacción, solo otra
// reacción la corta. Solo cuenta como dicho lo que de verdad se entregó a say() (handOff).

import type { Decision, Restriccion } from '../contract'
import { esSeguridad } from '../lib/decision-text'
import { SILENCIO_REPETIDA_MIN } from './frases'

/** Tope por tick: una ráfaga de bloqueos no debe encolar un minuto de audio. */
export const MAX_FRASES_POR_TICK = 2

/** El shock más reciente. `orderId` solo en un delay: la reacción es la decisión sobre ese pedido. */
export interface ShockRef {
  minute: number
  orderId: string | null
}

export interface NarrationState {
  /** `starts_at_min` del último shock cuya reacción ya se dijo. */
  narratedShock: number | null
  /** `order_id` de ese shock si fue un delay; null en los demás. */
  narratedOrder: string | null
  /** Clave de la frase (claveFrase) → minuto simulado en que se entregó a say() por última vez. */
  lastSaid: Record<string, number>
  /** Restricciones que ya sonaron en la sesión. */
  constraintsSaid: Restriccion[]
}

export interface NarrationPhrase {
  /** Lo que se dice, con sus números. */
  text: string
  /** Con qué se compara para no repetir (claveFrase). */
  key: string
  t: number
  restriccion: Restriccion | null
  /** Reacción o primera vez de su restricción. */
  priority: boolean
  /** La reacción a un shock. Implica `priority`. */
  reaction: boolean
}

export const initialNarration = (): NarrationState => ({
  narratedShock: null,
  narratedOrder: null,
  lastSaid: {},
  constraintsSaid: [],
})

/**
 * La frase con los números cambiados por #. No se usa la restricción sola: la capacidad de la
 * moto y el límite de kg comparten `vehicle_capacity` y dicen cosas distintas.
 */
export const claveFrase = (text: string): string => text.trim().replace(/\d+(?:[.,]\d+)?/g, '#')

const nivel = (p: NarrationPhrase) => (p.reaction ? 2 : p.priority ? 1 : 0)

/**
 * Las frases de un tick, por nivel (reacción, restricción nueva, normal) y a lo más
 * MAX_FRASES_POR_TICK. `lastShock` es el shock más reciente; un número es su `starts_at_min`
 * sin pedido. El estado que devuelve solo avanza el shock narrado: lo dicho se registra en handOff.
 */
export function phrasesToSay(
  newDecisions: Decision[],
  lastShock: number | ShockRef | null,
  state: NarrationState
): { phrases: NarrationPhrase[]; state: NarrationState } {
  const shock: ShockRef | null =
    typeof lastShock === 'number' ? { minute: lastShock, orderId: null } : lastShock
  const pendiente =
    shock !== null &&
    (shock.minute !== state.narratedShock || shock.orderId !== state.narratedOrder)
  const esReaccion = (d: Decision) =>
    shock !== null &&
    d.t >= shock.minute &&
    (shock.orderId === null || d.oferta_id === shock.orderId)
  const iReaccion = pendiente ? newDecisions.findIndex(esReaccion) : -1
  const narrado =
    shock && iReaccion >= 0
      ? { narratedShock: shock.minute, narratedOrder: shock.orderId }
      : { narratedShock: state.narratedShock, narratedOrder: state.narratedOrder }

  // Lo que ya entró en este tick también cuenta para no repetir y para la primera vez.
  const frasesDelTick = new Set<string>()
  const restriccionesDelTick = new Set<Restriccion>()
  const candidatas: NarrationPhrase[] = []

  newDecisions.forEach((d, i) => {
    const text = d.razon.trim()
    if (!text) return
    const key = claveFrase(text)
    const reaccion = i === iReaccion
    if (!reaccion) {
      if (!esSeguridad(d.restriccion)) return
      const ultima = state.lastSaid[key]
      const reciente = ultima !== undefined && d.t - ultima < SILENCIO_REPETIDA_MIN
      if (reciente || frasesDelTick.has(key)) return
    }
    const nueva =
      d.restriccion !== null &&
      esSeguridad(d.restriccion) &&
      !state.constraintsSaid.includes(d.restriccion) &&
      !restriccionesDelTick.has(d.restriccion)
    frasesDelTick.add(key)
    if (d.restriccion) restriccionesDelTick.add(d.restriccion)
    candidatas.push({
      text,
      key,
      t: d.t,
      restriccion: d.restriccion,
      priority: reaccion || nueva,
      reaction: reaccion,
    })
  })

  // Sort estable: por nivel, empates en el orden de las decisiones.
  const phrases = candidatas.sort((a, b) => nivel(b) - nivel(a)).slice(0, MAX_FRASES_POR_TICK)

  return { phrases, state: { ...state, ...narrado } }
}

/**
 * Qué frases entregar a say() dado si Nuez sigue hablando y si lo que suena es una reacción
 * (`reactionPlaying` solo cuenta con `speaking`). Hablando, las normales se sueltan y las de
 * prioridad interrumpen (`interrupt`: llamar callar() antes); con una reacción sonando solo otra
 * reacción interrumpe, y una restricción nueva se suelta sin registrar para que vuelva como
 * prioridad. Solo lo entregado se registra en el estado. `reaction`: `say[0]` es una reacción.
 */
export function handOff(
  phrases: NarrationPhrase[],
  speaking: boolean,
  state: NarrationState,
  reactionPlaying = false
): { say: string[]; interrupt: boolean; reaction: boolean; state: NarrationState } {
  const interrumpe = (p: NarrationPhrase) => (reactionPlaying ? p.reaction : p.priority)
  const entregadas = speaking ? phrases.filter(interrumpe) : phrases
  if (!entregadas.length) return { say: [], interrupt: false, reaction: false, state }

  const lastSaid = { ...state.lastSaid }
  const constraintsSaid = [...state.constraintsSaid]
  for (const p of entregadas) {
    lastSaid[p.key] = p.t
    const r = p.restriccion
    if (r && esSeguridad(r) && !constraintsSaid.includes(r)) constraintsSaid.push(r)
  }
  return {
    say: entregadas.map((p) => p.text),
    interrupt: speaking,
    reaction: entregadas[0].reaction,
    state: { ...state, lastSaid, constraintsSaid },
  }
}
