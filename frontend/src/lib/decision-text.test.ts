import { describe, it, expect } from 'vitest'
import {
  textoDecisionCorto,
  textoDecisionDetalle,
  etiquetaRestriccion,
  esSeguridad,
  tipoRestriccion,
} from './decision-text'
import type { Decision } from '../contract'

describe('esSeguridad', () => {
  it('null no es seguridad', () => {
    expect(esSeguridad(null)).toBe(false)
  })

  it('reservation_wage no es seguridad (es dinero)', () => {
    expect(esSeguridad('reservation_wage')).toBe(false)
  })

  it('flagged_zone_night sí es seguridad', () => {
    expect(esSeguridad('flagged_zone_night')).toBe(true)
  })

  it('heat_rule sí es seguridad', () => {
    expect(esSeguridad('heat_rule')).toBe(true)
  })

  it('vehicle_capacity no es seguridad (es un límite físico)', () => {
    expect(esSeguridad('vehicle_capacity')).toBe(false)
  })
})

describe('tipoRestriccion', () => {
  it('separa seguridad, capacidad y dinero', () => {
    expect(tipoRestriccion('flagged_zone_night')).toBe('safety')
    expect(tipoRestriccion('mandatory_break')).toBe('safety')
    expect(tipoRestriccion('heat_rule')).toBe('safety')
    expect(tipoRestriccion('shift_end_infeasible')).toBe('safety')
    expect(tipoRestriccion('vehicle_capacity')).toBe('capacity')
    expect(tipoRestriccion('reservation_wage')).toBe('money')
  })
})

describe('etiquetaRestriccion', () => {
  it('null → ""', () => {
    expect(etiquetaRestriccion(null)).toBe('')
  })

  it('reservation_wage → "Below wage"', () => {
    expect(etiquetaRestriccion('reservation_wage')).toBe('Below wage')
  })

  it('shift_end_infeasible → "Shift ends"', () => {
    expect(etiquetaRestriccion('shift_end_infeasible')).toBe('Shift ends')
  })
})

describe('textoDecisionCorto', () => {
  it('aceptar muestra edge positivo', () => {
    const d: Decision = {
      t: 0,
      oferta_id: 'o1',
      accion: 'aceptar',
      terminos: { pago_neto: 75, minutos: 19, ventaja: 71.5 },
      razon: '',
      restriccion: null,
    }
    const txt = textoDecisionCorto(d)
    expect(txt).toContain('Accept')
    expect(txt).toContain('MXN 75')
    expect(txt).toContain('19 min')
  })

  it('saltar por seguridad muestra la restricción', () => {
    const d: Decision = {
      t: 5,
      oferta_id: 'o2',
      accion: 'saltar',
      terminos: { pago_neto: 38, minutos: 25 },
      razon: '',
      restriccion: 'flagged_zone_night',
    }
    const txt = textoDecisionCorto(d)
    expect(txt).toContain('Skip')
    expect(txt).toContain('Flagged zone')
  })

  it('vehículo lleno sigue nombrando la restricción, aunque no sea seguridad', () => {
    const d: Decision = {
      t: 5,
      oferta_id: 'o2',
      accion: 'saltar',
      terminos: { pago_neto: 38, minutos: 25 },
      razon: '',
      restriccion: 'vehicle_capacity',
    }
    expect(textoDecisionCorto(d)).toBe('Skip: No capacity')
  })

  it('saltar por dinero muestra pago', () => {
    const d: Decision = {
      t: 5,
      oferta_id: 'o2',
      accion: 'saltar',
      terminos: { pago_neto: 38, minutos: 25 },
      razon: '',
      restriccion: 'reservation_wage',
    }
    const txt = textoDecisionCorto(d)
    expect(txt).toContain('Skip')
    expect(txt).toContain('MXN 38')
  })
})

describe('textoDecisionDetalle', () => {
  it('genera cuenta legible con todos los campos', () => {
    const d: Decision = {
      t: 3,
      oferta_id: 'o3',
      accion: 'saltar',
      terminos: {
        pago_neto: 30.6,
        minutos: 21.8,
        precio_tiempo: 51.6,
        ventaja: -21.0,
      },
      razon: '',
      restriccion: 'reservation_wage',
    }
    const txt = textoDecisionDetalle(d)
    expect(txt).toContain('Pays MXN 31')
    expect(txt).toContain('22 min')
    expect(txt).toContain('those min usually earn MXN 52')
    expect(txt).toContain('edge \u2212MXN 21')
  })
})
