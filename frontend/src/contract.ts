// GENERADO por scripts/contract_codegen.py a partir de contrato.py. NO EDITAR A MANO.
// Regenerar: python scripts/contract_codegen.py --write
//
// El tiempo SIEMPRE es minutos desde que empezo el turno (entero). Nunca fechas.

export type Accion = 'aceptar' | 'saltar'
export type Vehiculo = 'moto' | 'car' | 'bike'
export type Restriccion = 'flagged_zone_night' | 'mandatory_break' | 'heat_rule' | 'shift_end_infeasible' | 'vehicle_capacity' | 'reservation_wage'

export interface Punto {
  nombre: string
  lat: number
  lon: number
}

/** Lo que el estudiante llena antes de arrancar. */
export interface ConfigTurno {
  duracion_min: number
  ancla: Punto
  margen_min: number
  vehiculo: Vehiculo
  seed: number
  hora_inicio: number
  regresar_al_ancla: boolean
}

/** Un ping de la app. El simulador las emite, el motor las juzga. */
export interface Oferta {
  id: string
  plataforma: string
  pago: number
  surge: number
  t_aparece: number
  t_prep: number
  pickup: Punto
  dropoff: Punto
  peso_kg: number
  volumen_l: number
}

/** Dónde va y cómo va. Lo lee el front para pintar, y el motor para decidir. */
export interface EstadoRepartidor {
  t: number
  t_restante: number
  pos: Punto
  mochila: string[]
  ganado: number
  fatiga: number
  minutos_manejando: number
}

/** Por qué el motor hizo lo que hizo. Alimenta el front, la voz y el contrafactual. */
export interface Decision {
  t: number
  oferta_id: string
  accion: Accion
  terminos: Record<string, number>
  razon: string
  restriccion: Restriccion | null
}

/** Surge, cierre vial o lluvia. Lo dispara el simulador o el botón del juez. */
export interface EventoMundo {
  t: number
  tipo: 'surge' | 'cierre' | 'lluvia' | 'evento_masivo'
  zona: string
  duracion_min: number
  mult_demanda: number
  mult_tiempo: number
}
