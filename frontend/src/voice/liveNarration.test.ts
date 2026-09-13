import { describe, it, expect } from 'vitest'
import type { Decision, Restriccion } from '../contract'
import { SILENCIO_REPETIDA_MIN } from './frases'
import {
  MAX_FRASES_POR_TICK,
  handOff,
  initialNarration,
  phrasesToSay,
  type NarrationPhrase,
  type NarrationState,
} from './liveNarration'

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

const MOTO = 'En moto solo caben 3 pedidos a la vez.'
const FIN = 'No alcanzas a entregarlo y volver antes de que acabe tu turno.'

const seguridad = (t: number, razon = MOTO, restriccion: Restriccion = 'vehicle_capacity') =>
  dec({ t, restriccion, razon })

const estado = (cambio: Partial<NarrationState> = {}): NarrationState => ({
  ...initialNarration(),
  ...cambio,
})

/** Congela el estado para que cualquier mutación truene: las dos funciones son puras. */
const congelado = (s: NarrationState): NarrationState =>
  Object.freeze({
    ...s,
    lastSaid: Object.freeze({ ...s.lastSaid }),
    constraintsSaid: Object.freeze([...s.constraintsSaid]) as Restriccion[],
  })

const textos = (ps: NarrationPhrase[]) => ps.map((p) => p.text)

describe('phrasesToSay', () => {
  it('un bloqueo por seguridad se dice tal cual; la primera vez de su restricción es prioridad', () => {
    const r = phrasesToSay([seguridad(10)], null, congelado(initialNarration()))
    expect(r.phrases).toEqual([
      { text: MOTO, t: 10, restriccion: 'vehicle_capacity', priority: true },
    ])
    // Decir no es registrar: eso lo hace handOff cuando la frase de verdad va a say().
    expect(r.state).toEqual(initialNarration())
  })

  it('un salto por dinero y un aceptar de rutina sin shock se callan', () => {
    const r = phrasesToSay([dec(), dec({ accion: 'aceptar', restriccion: null })], null, estado())
    expect(r.phrases).toEqual([])
  })

  it('un salto por dinero antes del shock se calla y no gasta el shock', () => {
    const r = phrasesToSay([dec({ t: 29 })], 30, estado())
    expect(r).toEqual({ phrases: [], state: estado() })
  })

  it('la reacción al shock es prioridad, se dice una vez y la siguiente decisión se calla', () => {
    const primera = dec({ t: 30, razon: 'Salto: la ruta cruza el cierre.' })
    const r1 = phrasesToSay([primera], 30, congelado(estado()))
    expect(r1.phrases).toEqual([
      {
        text: 'Salto: la ruta cruza el cierre.',
        t: 30,
        restriccion: 'reservation_wage',
        priority: true,
      },
    ])
    expect(r1.state.narratedShock).toBe(30)

    const r2 = phrasesToSay([dec({ t: 33, razon: 'Otra que no paga.' })], 30, r1.state)
    expect(r2.phrases).toEqual([])
    expect(r2.state.narratedShock).toBe(30)
  })

  it('dentro del mismo tick solo la primera desde el shock cuenta', () => {
    const r = phrasesToSay(
      [
        dec({ t: 30, accion: 'aceptar', restriccion: null, razon: 'Tómala.' }),
        dec({ t: 30, razon: 'Esta no.' }),
      ],
      30,
      estado()
    )
    expect(textos(r.phrases)).toEqual(['Tómala.'])
  })

  it('un shock nuevo se vuelve a narrar', () => {
    const r1 = phrasesToSay([dec({ t: 30, razon: 'Por el cierre.' })], 30, estado())
    const r2 = phrasesToSay([dec({ t: 45, razon: 'Por el surge.' })], 44, r1.state)
    expect(textos(r2.phrases)).toEqual(['Por el surge.'])
    expect(r2.phrases[0].priority).toBe(true)
    expect(r2.state.narratedShock).toBe(44)
  })

  it('una decisión que es de seguridad y la reacción al shock se dice una sola vez', () => {
    const r = phrasesToSay([seguridad(31)], 30, estado())
    expect(r.phrases).toEqual([
      { text: MOTO, t: 31, restriccion: 'vehicle_capacity', priority: true },
    ])
  })

  it(`la misma frase de seguridad dentro de ${SILENCIO_REPETIDA_MIN} min se omite; a los ${SILENCIO_REPETIDA_MIN} vuelve`, () => {
    expect(SILENCIO_REPETIDA_MIN).toBe(15)
    const dicha = estado({ lastSaid: { [MOTO]: 6 }, constraintsSaid: ['vehicle_capacity'] })
    expect(phrasesToSay([seguridad(20)], null, dicha).phrases).toEqual([])
    expect(phrasesToSay([seguridad(21)], null, dicha).phrases).toEqual([
      { text: MOTO, t: 21, restriccion: 'vehicle_capacity', priority: false },
    ])
  })

  it('la misma frase dos veces en un tick se dice una vez', () => {
    const r = phrasesToSay([seguridad(7), seguridad(7)], null, estado())
    expect(textos(r.phrases)).toEqual([MOTO])
  })

  it('una restricción nueva es prioridad la primera vez y ya no después', () => {
    const kg = 'Son 30.5 kg y en moto el limite son 20 kg.'
    // En el mismo tick: la segunda frase de la misma restricción ya no es prioridad.
    const r1 = phrasesToSay([seguridad(77, kg), seguridad(77)], null, estado())
    expect(r1.phrases.map((p) => p.priority)).toEqual([true, false])

    const ya = estado({ constraintsSaid: ['vehicle_capacity'] })
    expect(phrasesToSay([seguridad(79, kg)], null, ya).phrases[0].priority).toBe(false)
    expect(phrasesToSay([seguridad(43, FIN, 'shift_end_infeasible')], null, ya).phrases).toEqual([
      { text: FIN, t: 43, restriccion: 'shift_end_infeasible', priority: true },
    ])
  })

  it('con la reacción al shock ya narrada, un bloqueo por seguridad se sigue diciendo', () => {
    const narrado = estado({ narratedShock: 30, constraintsSaid: ['vehicle_capacity'] })
    const r = phrasesToSay([seguridad(43, FIN, 'shift_end_infeasible'), seguridad(43)], 30, narrado)
    expect(textos(r.phrases)).toEqual([FIN, MOTO])
    expect(r.state.narratedShock).toBe(30)
  })

  it('el tope de dos por tick guarda primero las de prioridad; empates en orden de decisión', () => {
    const ya = estado({ constraintsSaid: ['vehicle_capacity'] })
    const r = phrasesToSay(
      [
        seguridad(50, 'Uno.'),
        seguridad(50, 'Dos.'),
        seguridad(50, 'Llevas 90 min bajo el sol.', 'heat_rule'),
      ],
      null,
      ya
    )
    expect(MAX_FRASES_POR_TICK).toBe(2)
    expect(textos(r.phrases)).toEqual(['Llevas 90 min bajo el sol.', 'Uno.'])
  })

  it('al cortar, la reacción al shock no se pierde aunque llegue después de seguridades', () => {
    const ya = estado({ constraintsSaid: ['vehicle_capacity'] })
    const r = phrasesToSay(
      [seguridad(28, 'Uno.'), seguridad(29, 'Dos.'), dec({ t: 30, razon: 'Reacción.' })],
      30,
      ya
    )
    expect(textos(r.phrases)).toEqual(['Reacción.', 'Uno.'])
  })

  it('una razón vacía no ocupa lugar, pero la reacción al shock sí se da por narrada', () => {
    const r = phrasesToSay([dec({ t: 30, razon: '  ' }), seguridad(30)], 30, estado())
    expect(textos(r.phrases)).toEqual([MOTO])
    expect(r.state.narratedShock).toBe(30)
  })

  it('sin decisiones no cambia nada', () => {
    expect(phrasesToSay([], 30, estado())).toEqual({ phrases: [], state: estado() })
    const previo = estado({ narratedShock: 12 })
    expect(phrasesToSay([], 30, previo)).toEqual({ phrases: [], state: previo })
  })
})

describe('handOff', () => {
  const normal: NarrationPhrase = {
    text: MOTO,
    t: 21,
    restriccion: 'vehicle_capacity',
    priority: false,
  }
  const prioridad: NarrationPhrase = {
    text: FIN,
    t: 21,
    restriccion: 'shift_end_infeasible',
    priority: true,
  }

  it('en silencio entrega todo, sin interrumpir, y registra minuto y restricción', () => {
    const r = handOff([prioridad, normal], false, congelado(estado({ lastSaid: { [MOTO]: 6 } })))
    expect(r.say).toEqual([FIN, MOTO])
    expect(r.interrupt).toBe(false)
    expect(r.state.lastSaid).toEqual({ [MOTO]: 21, [FIN]: 21 })
    expect(r.state.constraintsSaid).toEqual(['shift_end_infeasible', 'vehicle_capacity'])
  })

  it('hablando, suelta las normales sin registrarlas y la de prioridad interrumpe', () => {
    const r = handOff([prioridad, normal], true, congelado(estado({ lastSaid: { [MOTO]: 6 } })))
    expect(r.say).toEqual([FIN])
    expect(r.interrupt).toBe(true)
    expect(r.state.lastSaid).toEqual({ [MOTO]: 6, [FIN]: 21 })
    expect(r.state.constraintsSaid).toEqual(['shift_end_infeasible'])
  })

  it('hablando y sin prioridad no entrega nada ni cambia el estado', () => {
    const previo = estado({ lastSaid: { [MOTO]: 6 }, constraintsSaid: ['vehicle_capacity'] })
    expect(handOff([normal], true, previo)).toEqual({ say: [], interrupt: false, state: previo })
  })
})

// ── Seed 2005, 14:00, moto, Tec, cierre de Constitución en el minuto 30 ──
// Las decisiones de Nuez de t=0 a t=60, sacadas del backend (/live/tick) con ese mismo turno.
// [minuto, restricción, razón]; sin restricción es un aceptar.
const P = MOTO
const F = FIN
const SEED_2005: [number, Restriccion | null, string][] = [
  [0, null, 'Te deja $132 por encima de lo normal.'],
  [1, null, 'Te deja $24 por encima de lo normal.'],
  [2, 'reservation_wage', 'Esos 27 minutos rinden $77 normalmente, y este paga $51.'],
  [3, 'reservation_wage', 'Esos 21 minutos rinden $58 normalmente, y este paga $51.'],
  [4, null, 'Te deja $37 por encima de lo normal.'],
  ...[6, 7, 8, 9, 10, 12, 14, 15, 16, 17, 18, 19, 20, 21, 24, 25, 26].map(
    (t) => [t, 'vehicle_capacity', P] as [number, Restriccion, string]
  ),
  [27, 'reservation_wage', 'Esos 27 minutos rinden $78 normalmente, y este paga $31.'],
  [28, 'reservation_wage', 'Esos 21 minutos rinden $62 normalmente, y este paga $41.'],
  [29, null, 'Te deja $26 por encima de lo normal.'],
  [32, null, 'Te deja $40 por encima de lo normal.'],
  ...[34, 35, 36, 37, 39, 40, 41, 42].map(
    (t) => [t, 'vehicle_capacity', P] as [number, Restriccion, string]
  ),
  ...[43, 44, 46].map((t) => [t, 'shift_end_infeasible', F] as [number, Restriccion, string]),
  [48, null, 'Te deja $7 por encima de lo normal.'],
  ...[49, 50, 51, 52, 53, 54].map(
    (t) => [t, 'vehicle_capacity', P] as [number, Restriccion, string]
  ),
  [55, 'shift_end_infeasible', F],
  [56, null, 'Te deja $1 por encima de lo normal.'],
  ...[58, 59, 60].map((t) => [t, 'vehicle_capacity', P] as [number, Restriccion, string]),
]

/** El turno como lo corre la página: un tick por minuto, y cada entrega a say() deja a
 *  Nuez hablando `minutosHablando` minutos simulados (o hasta que otra la interrumpe). */
function replay(minutosHablando: number): [number, string][] {
  let state = initialNarration()
  let hablaHasta = -1
  const dichas: [number, string][] = []
  for (let t = 0; t <= 60; t++) {
    const decisiones = SEED_2005.filter(([m]) => m === t).map(([m, restriccion, razon]) =>
      dec({ t: m, restriccion, razon, accion: restriccion ? 'saltar' : 'aceptar' })
    )
    const r = phrasesToSay(decisiones, t >= 30 ? 30 : null, state)
    const h = handOff(r.phrases, t < hablaHasta, r.state)
    state = h.state
    if (h.say.length) hablaHasta = t + minutosHablando
    for (const texto of h.say) dichas.push([t, texto])
  }
  return dichas
}

function motoCadaQuince(dichas: [number, string][]) {
  const minutos = dichas.filter(([, x]) => x === MOTO).map(([t]) => t)
  minutos.slice(1).forEach((t, i) => expect(t - minutos[i]).toBeGreaterThanOrEqual(15))
}

describe('replay de seed 2005 (t=0–60)', () => {
  it('sin solaparse: cada restricción nueva suena, la moto a lo más cada 15 min', () => {
    const dichas = replay(0)
    expect(dichas).toEqual([
      [6, MOTO],
      [21, MOTO],
      [32, 'Te deja $40 por encima de lo normal.'],
      [36, MOTO],
      [43, FIN],
      [51, MOTO],
    ])
    motoCadaQuince(dichas)
  })

  it('con frases de 8 min: lo soltado no cuenta como dicho y el primer fin de turno interrumpe', () => {
    const dichas = replay(8)
    // t=36–39 caen mientras habla la reacción: se sueltan sin registrar, y la moto vuelve en t=40.
    expect(dichas).toEqual([
      [6, MOTO],
      [21, MOTO],
      [32, 'Te deja $40 por encima de lo normal.'],
      [40, MOTO],
      [43, FIN],
      [58, MOTO],
    ])
    motoCadaQuince(dichas)
  })
})
