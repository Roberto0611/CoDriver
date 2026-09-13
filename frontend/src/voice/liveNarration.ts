// Qué dice Nuez en voz alta en el turno en vivo. A diferencia del replay (frases.ts), aquí
// no se sabe de antemano qué va a pasar: no hay prefetch y se dice la `razon` tal cual,
// en español, con la voz de ElevenLabs configurada para eso.
//
// Solo dos cosas se dicen: cada bloqueo por seguridad, y la primera decisión desde que
// empezó un shock (la reacción de Nuez al cierre o al surge), una vez por shock. Lo demás
// (aceptar de rutina, saltos por dinero) pasa casi cada minuto y taparía lo importante.

import type { Decision } from '../contract'
import { esSeguridad } from '../lib/decision-text'

/** Tope por tick: una ráfaga de bloqueos no debe encolar un minuto de audio. */
export const MAX_FRASES_POR_TICK = 2

/**
 * Las frases de un tick. `lastShockMinute` es el `starts_at_min` del shock más reciente;
 * `narratedShock` el del último shock cuya reacción ya se dijo. Devuelve el nuevo
 * `narratedShock` para guardarlo hasta el siguiente tick.
 */
export function phrasesToSay(
  newDecisions: Decision[],
  lastShockMinute: number | null,
  narratedShock: number | null
): { phrases: string[]; narratedShock: number | null } {
  const pendiente = lastShockMinute !== null && lastShockMinute !== narratedShock
  const iReaccion = pendiente ? newDecisions.findIndex((d) => d.t >= lastShockMinute) : -1
  const narrado = iReaccion >= 0 ? lastShockMinute : narratedShock

  // Una decisión que es a la vez seguridad y reacción entra una sola vez.
  const candidatas = newDecisions
    .map((d, i) => ({ texto: d.razon.trim(), i, reaccion: i === iReaccion }))
    .filter((c) => c.texto && (c.reaccion || esSeguridad(newDecisions[c.i].restriccion)))

  // Al cortar gana la reacción al shock; lo que queda sale en el orden de las decisiones.
  const elegidas = [...candidatas]
    .sort((a, b) => Number(b.reaccion) - Number(a.reaccion))
    .slice(0, MAX_FRASES_POR_TICK)
    .sort((a, b) => a.i - b.i)

  return { phrases: elegidas.map((c) => c.texto), narratedShock: narrado }
}
