import { describe, it, expect } from 'vitest'
import { fraseVoz, siguienteFrase, frasesDelTurno, debeCallar } from './frases'
import type { Decision } from '../contract'
import type { Frame } from '../lib/turno'

function dec(overrides: Partial<Decision> = {}): Decision {
  return {
    t: 0,
    oferta_id: 'o_000',
    accion: 'saltar',
    terminos: { pago_neto: 52.8, minutos: 23.8 },
    razon: 'Te deja $45 por encima de lo normal.',
    restriccion: null,
    ...overrides,
  }
}

function frame(t: number, decisiones: Decision[]): Frame {
  return { t, ofertas: [], decisiones, llegada: null, cobro: 0, ganado: 0 }
}

describe('fraseVoz', () => {
  it('aceptar dice pago y minutos redondeados, en inglés', () => {
    expect(fraseVoz(dec({ accion: 'aceptar' }), 'moto')).toBe('Take it. 53 pesos for 24 minutes.')
  })

  it('un salto por dinero no se dice: sería ruido cada minuto', () => {
    expect(fraseVoz(dec({ restriccion: 'reservation_wage' }), 'moto')).toBeNull()
    expect(fraseVoz(dec(), 'moto')).toBeNull()
  })

  it('cada restricción de seguridad tiene su frase y nombra la regla', () => {
    expect(fraseVoz(dec({ restriccion: 'heat_rule' }), 'moto')).toMatch(/heat/i)
    expect(fraseVoz(dec({ restriccion: 'mandatory_break' }), 'moto')).toMatch(/break/i)
    expect(fraseVoz(dec({ restriccion: 'flagged_zone_night' }), 'moto')).toMatch(/10 PM|night/i)
    expect(fraseVoz(dec({ restriccion: 'shift_end_infeasible' }), 'moto')).toMatch(/shift/i)
  })

  it('la capacidad nombra el vehículo', () => {
    expect(fraseVoz(dec({ restriccion: 'vehicle_capacity' }), 'bike')).toMatch(/bike/)
    expect(fraseVoz(dec({ restriccion: 'vehicle_capacity' }), 'car')).toMatch(/car/)
  })

  it('no lee la razon en español', () => {
    expect(fraseVoz(dec({ accion: 'aceptar' }), 'moto')).not.toContain('Te deja')
  })
})

describe('siguienteFrase', () => {
  const calor = dec({ restriccion: 'heat_rule' })

  it('prefiere aceptar sobre un rechazo en el mismo minuto', () => {
    const r = siguienteFrase([calor, dec({ accion: 'aceptar' })], 5, 'moto', null)
    expect(r?.frase).toMatch(/^Take it/)
  })

  it('no repite la misma frase seguida hasta que pase el silencio', () => {
    const primera = siguienteFrase([calor], 10, 'moto', null)
    expect(primera).not.toBeNull()
    expect(siguienteFrase([calor], 12, 'moto', primera)).toBeNull()
    expect(siguienteFrase([calor], 25, 'moto', primera)).not.toBeNull()
  })

  it('una frase distinta sí suena aunque sea pronto', () => {
    const primera = siguienteFrase([calor], 10, 'moto', null)
    const r = siguienteFrase([dec({ restriccion: 'shift_end_infeasible' })], 11, 'moto', primera)
    expect(r?.frase).toMatch(/shift/i)
  })

  it('un minuto sin nada que decir devuelve null', () => {
    expect(siguienteFrase([dec()], 3, 'moto', null)).toBeNull()
  })
})

describe('debeCallar', () => {
  const ULTIMO = 119

  it('avanzar un minuto reproduciendo no corta la frase', () => {
    expect(debeCallar(40, 41, true, ULTIMO)).toBe(false)
  })

  it('un seek a mano corta la frase, hacia atrás o hacia adelante', () => {
    expect(debeCallar(40, 10, true, ULTIMO)).toBe(true)
    expect(debeCallar(40, 90, true, ULTIMO)).toBe(true)
  })

  it('pausar a media sesión corta la frase', () => {
    expect(debeCallar(40, 40, false, ULTIMO)).toBe(true)
  })

  it('cuando el turno se detiene solo en el último minuto, la última frase termina', () => {
    expect(debeCallar(ULTIMO, ULTIMO, false, ULTIMO)).toBe(false)
  })

  it('cambiar solo el play sin mover el minuto no cuenta como seek', () => {
    expect(debeCallar(40, 40, true, ULTIMO)).toBe(false)
  })
})

describe('frasesDelTurno', () => {
  it('lista sin duplicados lo que el narrador diría en el turno completo', () => {
    const frames = [
      frame(0, [dec({ accion: 'aceptar' })]),
      frame(1, [dec({ restriccion: 'heat_rule' })]),
      frame(2, [dec({ restriccion: 'heat_rule' })]),
      frame(30, [dec({ restriccion: 'heat_rule' })]),
      frame(31, [dec()]),
    ]
    expect(frasesDelTurno(frames, 'moto')).toEqual([
      'Take it. 53 pesos for 24 minutes.',
      fraseVoz(dec({ restriccion: 'heat_rule' }), 'moto'),
    ])
  })
})
