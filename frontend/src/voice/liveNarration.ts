// Qué dice Nuez en voz alta en el turno en vivo. A diferencia del replay (frases.ts), aquí
// no se sabe de antemano qué va a pasar: no hay prefetch y se dice la `razon` tal cual,
// en español, con la voz de ElevenLabs configurada para eso.
//
// Se dicen dos cosas:
// - la reacción de Nuez a un shock: la primera decisión desde `starts_at_min`, una vez por
//   shock, aunque sea un aceptar o un salto por dinero;
// - los bloqueos por seguridad, salvo que esa misma frase ya haya sonado en los últimos
//   SILENCIO_REPETIDA_MIN minutos (la misma regla que /sim). Hay turnos con un bloqueo casi
//   cada minuto, y todos dicen lo mismo.
// Lo demás (aceptar de rutina, saltos por dinero) taparía lo importante.
//
// Prioridad: la reacción al shock y la primera vez que suena cada restricción. Una frase con
// prioridad corta lo que Nuez esté diciendo; una normal se suelta si Nuez sigue hablando.
// Solo cuenta como dicho lo que de verdad se entregó a say() (handOff).

import type { Decision, Restriccion } from '../contract'
import { esSeguridad } from '../lib/decision-text'
import { SILENCIO_REPETIDA_MIN } from './frases'

/** Tope por tick: una ráfaga de bloqueos no debe encolar un minuto de audio. */
export const MAX_FRASES_POR_TICK = 2

export interface NarrationState {
  /** `starts_at_min` del último shock cuya reacción ya se dijo. */
  narratedShock: number | null
  /** Frase (`razon.trim()`) → minuto simulado en que se entregó a say() por última vez. */
  lastSaid: Record<string, number>
  /** Restricciones que ya sonaron en la sesión. */
  constraintsSaid: Restriccion[]
}

export interface NarrationPhrase {
  text: string
  t: number
  restriccion: Restriccion | null
  priority: boolean
}

export const initialNarration = (): NarrationState => ({
  narratedShock: null,
  lastSaid: {},
  constraintsSaid: [],
})

/**
 * Las frases de un tick, con prioridad primero y a lo más MAX_FRASES_POR_TICK.
 * `lastShockMinute` es el `starts_at_min` del shock más reciente. El estado que devuelve
 * solo avanza `narratedShock`: lo dicho se registra en handOff.
 */
export function phrasesToSay(
  newDecisions: Decision[],
  lastShockMinute: number | null,
  state: NarrationState
): { phrases: NarrationPhrase[]; state: NarrationState } {
  const pendiente = lastShockMinute !== null && lastShockMinute !== state.narratedShock
  const iReaccion = pendiente ? newDecisions.findIndex((d) => d.t >= lastShockMinute) : -1
  const narratedShock = iReaccion >= 0 ? lastShockMinute : state.narratedShock

  // Lo que ya entró en este tick también cuenta para no repetir y para la primera vez.
  const frasesDelTick = new Set<string>()
  const restriccionesDelTick = new Set<Restriccion>()
  const candidatas: NarrationPhrase[] = []

  newDecisions.forEach((d, i) => {
    const text = d.razon.trim()
    if (!text) return
    const reaccion = i === iReaccion
    if (!reaccion) {
      if (!esSeguridad(d.restriccion)) return
      const ultima = state.lastSaid[text]
      const reciente = ultima !== undefined && d.t - ultima < SILENCIO_REPETIDA_MIN
      if (reciente || frasesDelTick.has(text)) return
    }
    const nueva =
      d.restriccion !== null &&
      esSeguridad(d.restriccion) &&
      !state.constraintsSaid.includes(d.restriccion) &&
      !restriccionesDelTick.has(d.restriccion)
    frasesDelTick.add(text)
    if (d.restriccion) restriccionesDelTick.add(d.restriccion)
    candidatas.push({ text, t: d.t, restriccion: d.restriccion, priority: reaccion || nueva })
  })

  // Sort estable: prioridad primero, empates en el orden de las decisiones.
  const phrases = candidatas
    .sort((a, b) => Number(b.priority) - Number(a.priority))
    .slice(0, MAX_FRASES_POR_TICK)

  return { phrases, state: { ...state, narratedShock } }
}

/**
 * Qué frases entregar a say() dado si Nuez sigue hablando. Hablando, las normales se
 * sueltan y las de prioridad interrumpen (`interrupt`: llamar callar() antes). Solo lo
 * entregado se registra en el estado.
 */
export function handOff(
  phrases: NarrationPhrase[],
  speaking: boolean,
  state: NarrationState
): { say: string[]; interrupt: boolean; state: NarrationState } {
  const entregadas = speaking ? phrases.filter((p) => p.priority) : phrases
  if (!entregadas.length) return { say: [], interrupt: false, state }

  const lastSaid = { ...state.lastSaid }
  const constraintsSaid = [...state.constraintsSaid]
  for (const p of entregadas) {
    lastSaid[p.text] = p.t
    const r = p.restriccion
    if (r && esSeguridad(r) && !constraintsSaid.includes(r)) constraintsSaid.push(r)
  }
  return {
    say: entregadas.map((p) => p.text),
    interrupt: speaking,
    state: { ...state, lastSaid, constraintsSaid },
  }
}
