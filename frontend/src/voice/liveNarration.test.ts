import { describe, it, expect } from 'vitest'
import type { Decision } from '../contract'
import { MAX_FRASES_POR_TICK, phrasesToSay } from './liveNarration'

function dec(overrides: Partial<Decision> = {}): Decision {
  return {
    t: 10,
    oferta_id: 'o_000',
    accion: 'saltar',
    terminos: { pago_neto: 40, minutos: 20 },
    razon: 'Te deja menos de lo que ganas en ese tiempo.',
    restriccion: 'reservation_wage',
    ...overrides,
  }
}

const seguridad = (t: number, razon = 'No te mando a una zona marcada de noche.') =>
  dec({ t, restriccion: 'flagged_zone_night', razon })

describe('phrasesToSay', () => {
  it('un bloqueo por seguridad se dice, con la razón tal cual', () => {
    const r = phrasesToSay([seguridad(10)], null, null)
    expect(r.phrases).toEqual(['No te mando a una zona marcada de noche.'])
    expect(r.narratedShock).toBeNull()
  })

  it('un salto por dinero sin shock se calla', () => {
    expect(phrasesToSay([dec()], null, null)).toEqual({ phrases: [], narratedShock: null })
  })

  it('un aceptar sin shock se calla', () => {
    const r = phrasesToSay([dec({ accion: 'aceptar', restriccion: null })], null, null)
    expect(r.phrases).toEqual([])
  })

  it('un salto por dinero antes del shock se calla y no gasta el shock', () => {
    const r = phrasesToSay([dec({ t: 29 })], 30, null)
    expect(r).toEqual({ phrases: [], narratedShock: null })
  })

  it('la primera decisión desde el shock se dice una vez; la siguiente se calla', () => {
    const primera = dec({ t: 30, razon: 'Salto: la ruta cruza el cierre.' })
    const r1 = phrasesToSay([primera], 30, null)
    expect(r1).toEqual({ phrases: ['Salto: la ruta cruza el cierre.'], narratedShock: 30 })

    const segunda = dec({ t: 33, razon: 'Otra que no paga.' })
    const r2 = phrasesToSay([segunda], 30, r1.narratedShock)
    expect(r2).toEqual({ phrases: [], narratedShock: 30 })
  })

  it('dentro del mismo tick solo la primera desde el shock cuenta', () => {
    const r = phrasesToSay(
      [
        dec({ t: 30, accion: 'aceptar', restriccion: null, razon: 'Tómala.' }),
        dec({ t: 30, razon: 'Esta no.' }),
      ],
      30,
      null
    )
    expect(r).toEqual({ phrases: ['Tómala.'], narratedShock: 30 })
  })

  it('un shock nuevo se vuelve a narrar', () => {
    const r1 = phrasesToSay([dec({ t: 30, razon: 'Por el cierre.' })], 30, null)
    const r2 = phrasesToSay([dec({ t: 45, razon: 'Por el surge.' })], 44, r1.narratedShock)
    expect(r2).toEqual({ phrases: ['Por el surge.'], narratedShock: 44 })
  })

  it('una decisión que es de seguridad y la primera tras el shock se dice una sola vez', () => {
    const r = phrasesToSay([seguridad(31, 'Zona marcada.')], 30, null)
    expect(r).toEqual({ phrases: ['Zona marcada.'], narratedShock: 30 })
  })

  it('más de dos candidatas en un tick se cortan a dos', () => {
    const r = phrasesToSay(
      [seguridad(50, 'Uno.'), seguridad(50, 'Dos.'), seguridad(50, 'Tres.')],
      null,
      null
    )
    expect(MAX_FRASES_POR_TICK).toBe(2)
    expect(r.phrases).toEqual(['Uno.', 'Dos.'])
  })

  it('al cortar, la reacción al shock no se pierde aunque llegue después de seguridades', () => {
    // Un tick de varios minutos: dos bloqueos antes del shock y la reacción al final.
    const r = phrasesToSay(
      [seguridad(28, 'Uno.'), seguridad(29, 'Dos.'), dec({ t: 30, razon: 'Reacción.' })],
      30,
      null
    )
    expect(r).toEqual({ phrases: ['Uno.', 'Reacción.'], narratedShock: 30 })
  })

  it('una razón vacía no ocupa lugar, pero la reacción al shock sí se da por narrada', () => {
    const r = phrasesToSay([dec({ t: 30, razon: '  ' }), seguridad(30, 'Zona.')], 30, null)
    expect(r).toEqual({ phrases: ['Zona.'], narratedShock: 30 })
  })

  it('sin decisiones no cambia nada', () => {
    expect(phrasesToSay([], 30, null)).toEqual({ phrases: [], narratedShock: null })
    expect(phrasesToSay([], 30, 12)).toEqual({ phrases: [], narratedShock: 12 })
  })
})
