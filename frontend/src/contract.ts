// GENERADO por scripts/contract_codegen.py a partir de contrato.py. NO EDITAR A MANO.
// Regenerar: python scripts/contract_codegen.py --write
//
// El tiempo SIEMPRE es minutos desde que empezo el turno (entero). Nunca fechas.

export type Accion = 'aceptar' | 'saltar'
export type Vehiculo = 'moto' | 'bici' | 'scooter' | 'pie'
export type Restriccion = 'regreso_infactible' | 'zona_insegura' | 'mochila_llena'

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
}

/** Dónde va y cómo va. Lo lee el front para pintar, y el motor para decidir. */
export interface EstadoRepartidor {
  t: number
  t_restante: number
  pos: Punto
  mochila: string[]
  ganado: number
  fatiga: number
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
