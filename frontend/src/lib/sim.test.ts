import { describe, it, expect } from 'vitest'
import {
  distanciaAcumulada,
  interpolarSobreLinea,
  posicionEnMinuto,
  minutosAHora,
  contadoresEnT,
} from './sim'
import type { Tramo, Frame } from './turno'
import type { ConfigTurno } from '../contract'

// ── Helpers ──────────────────────────────────────────────────────────────

const config: ConfigTurno = {
  duracion_min: 120,
  ancla: { nombre: 'Tec', lat: 25.6476, lon: -100.2898 },
  margen_min: 10,
  vehiculo: 'moto',
  seed: 42,
  hora_inicio: 14,
}

// Puntos falsos (GeoJSON con 3 features)
const puntos: GeoJSON.FeatureCollection = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', geometry: { type: 'Point', coordinates: [-100.29, 25.65] }, properties: { i: 0 } },
    { type: 'Feature', geometry: { type: 'Point', coordinates: [-100.30, 25.66] }, properties: { i: 1 } },
    { type: 'Feature', geometry: { type: 'Point', coordinates: [-100.31, 25.67] }, properties: { i: 2 } },
  ],
}

const tramos: Tramo[] = [
  { t_salida: 5, t_llegada: 15, desde: 0, hasta: 1, clave: '0-1' },
  { t_salida: 20, t_llegada: 30, desde: 1, hasta: 2, clave: '1-2' },
]

// Polilínea simple de 3 puntos (segmentos iguales)
const geometria: Record<string, [number, number][]> = {
  '0-1': [[-100.29, 25.65], [-100.295, 25.655], [-100.30, 25.66]],
  '1-2': [[-100.30, 25.66], [-100.305, 25.665], [-100.31, 25.67]],
}

// ── Tests ────────────────────────────────────────────────────────────────

describe('distanciaAcumulada', () => {
  it('devuelve [0] para un solo punto', () => {
    expect(distanciaAcumulada([[-100, 25]])).toEqual([0])
  })

  it('acumula distancias correctamente', () => {
    const d = distanciaAcumulada([[-100, 25], [-100, 26], [-100, 28]])
    expect(d[0]).toBe(0)
    expect(d[1]).toBeCloseTo(1)
    expect(d[2]).toBeCloseTo(3) // 1 + 2
  })
})

describe('interpolarSobreLinea', () => {
  const line: [number, number][] = [
    [0, 0],
    [10, 0],
    [10, 10],
  ]

  it('frac=0 devuelve el inicio', () => {
    expect(interpolarSobreLinea(line, 0)).toEqual([0, 0])
  })

  it('frac=1 devuelve el final', () => {
    expect(interpolarSobreLinea(line, 1)).toEqual([10, 10])
  })

  it('frac=0.5 devuelve el punto medio por distancia', () => {
    const mid = interpolarSobreLinea(line, 0.5)
    // Total = 10 + 10 = 20, mitad = 10 → exactamente en la esquina
    expect(mid[0]).toBeCloseTo(10)
    expect(mid[1]).toBeCloseTo(0)
  })
})

describe('posicionEnMinuto', () => {
  it('antes del primer tramo devuelve el ancla', () => {
    const pos = posicionEnMinuto(0, tramos, geometria, config, puntos)
    expect(pos).toEqual([config.ancla.lon, config.ancla.lat])
  })

  it('durante un tramo interpola sobre la geometría', () => {
    // t=10 está a la mitad del tramo 0-1 (5 a 15, frac=0.5)
    const pos = posicionEnMinuto(10, tramos, geometria, config, puntos)
    // Mitad de la polilínea [-100.29,25.65] → [-100.295,25.655] → [-100.30,25.66]
    expect(pos[0]).toBeCloseTo(-100.295)
    expect(pos[1]).toBeCloseTo(25.655)
  })

  it('entre tramos devuelve el hasta del último terminado', () => {
    // t=17 es entre tramo 0-1 (termina t=15) y tramo 1-2 (empieza t=20)
    const pos = posicionEnMinuto(17, tramos, geometria, config, puntos)
    // punto 1 = [-100.30, 25.66]
    expect(pos).toEqual([-100.30, 25.66])
  })

  it('después del último tramo devuelve el último hasta', () => {
    const pos = posicionEnMinuto(50, tramos, geometria, config, puntos)
    expect(pos).toEqual([-100.31, 25.67])
  })
})

describe('minutosAHora', () => {
  it('14:00 + 0 → "14:00"', () => {
    expect(minutosAHora(14, 0)).toBe('14:00')
  })

  it('14:00 + 25 → "14:25"', () => {
    expect(minutosAHora(14, 25)).toBe('14:25')
  })

  it('14:00 + 90 → "15:30"', () => {
    expect(minutosAHora(14, 90)).toBe('15:30')
  })

  it('14:00 + 120 → "16:00"', () => {
    expect(minutosAHora(14, 120)).toBe('16:00')
  })
})

describe('contadoresEnT', () => {
  const frames: Frame[] = [
    {
      t: 0, ofertas: [], decisiones: [
        { t: 0, oferta_id: 'o1', accion: 'aceptar', terminos: {}, razon: '', restriccion: null },
      ],
      llegada: null, cobro: 0, ganado: 0,
    },
    {
      t: 1, ofertas: [], decisiones: [
        { t: 1, oferta_id: 'o2', accion: 'saltar', terminos: {}, razon: '', restriccion: 'reservation_wage' },
      ],
      llegada: null, cobro: 50, ganado: 50,
    },
    {
      t: 2, ofertas: [], decisiones: [],
      llegada: null, cobro: 0, ganado: 50,
    },
  ]

  it('t=0: 0 entregas, 0 saltadas, ganado=0', () => {
    const c = contadoresEnT(frames, 0)
    expect(c.entregas).toBe(0)
    expect(c.saltadas).toBe(0)
    expect(c.ganado).toBe(0)
  })

  it('t=1: 1 entrega, 1 saltada, ganado=50', () => {
    const c = contadoresEnT(frames, 1)
    expect(c.entregas).toBe(1)
    expect(c.saltadas).toBe(1)
    expect(c.ganado).toBe(50)
  })

  it('t=2: 1 entrega (no sube sin cobro nuevo), ganado=50', () => {
    const c = contadoresEnT(frames, 2)
    expect(c.entregas).toBe(1)
    expect(c.saltadas).toBe(1)
    expect(c.ganado).toBe(50)
  })
})
