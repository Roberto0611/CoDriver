import { describe, it, expect } from 'vitest'

import { entregasTexto, horaDeRegreso } from './countersCopy'

describe('horaDeRegreso', () => {
  it('el turno ensayado: 120 min desde las 14:00 con 10 de margen vuelve a las 15:50', () => {
    expect(horaDeRegreso({ hora_inicio: 14, duracion_min: 120, margen_min: 10 })).toBe('15:50')
  })

  it('un turno de 8 h desde las 16:00 vuelve a las 23:50', () => {
    expect(horaDeRegreso({ hora_inicio: 16, duracion_min: 480, margen_min: 10 })).toBe('23:50')
  })

  it('pasa la medianoche sin inventar la hora 24', () => {
    expect(horaDeRegreso({ hora_inicio: 22, duracion_min: 480, margen_min: 10 })).toBe('05:50')
    expect(horaDeRegreso({ hora_inicio: 20, duracion_min: 250, margen_min: 10 })).toBe('00:00')
    expect(horaDeRegreso({ hora_inicio: 23, duracion_min: 120, margen_min: 10 })).toBe('00:50')
  })

  it('un turno que arranca a medianoche o de madrugada no se corre de día', () => {
    expect(horaDeRegreso({ hora_inicio: 0, duracion_min: 120, margen_min: 10 })).toBe('01:50')
    expect(horaDeRegreso({ hora_inicio: 2, duracion_min: 480, margen_min: 10 })).toBe('09:50')
  })

  it('respeta duraciones que no son múltiplos de 10 y otro margen', () => {
    expect(horaDeRegreso({ hora_inicio: 9, duracion_min: 95, margen_min: 15 })).toBe('10:20')
  })
})

describe('entregasTexto', () => {
  it('singular solo para una', () => {
    expect(entregasTexto(1)).toBe('1 delivery')
  })

  it('plural para cero y para varias', () => {
    expect(entregasTexto(0)).toBe('0 deliveries')
    expect(entregasTexto(5)).toBe('5 deliveries')
  })
})
