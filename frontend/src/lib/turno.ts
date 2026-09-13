// Tipos para los turnos grabados (turno_greedy_*.json / turno_nuez_*.json).
// Reflejan la estructura exportada por data/export_turno.py.
// No se edita contract.ts (es autogenerado por contract_codegen.py).

import type { Oferta, Decision, ConfigTurno } from '../contract'

/** Metadatos resumen del turno completo. */
export interface TurnoMeta {
  politica: 'greedy' | 'nuez'
  seed: number
  ganado: number
  /** Opcionales para que los turnos grabados previos sigan reproduciéndose. */
  ingreso_bruto?: number
  gasto_combustible?: number
  entregas: number
  rechazos: number
  ofertas_totales: number
  violaciones: number
  llego_tarde: boolean
  regreso_en: number
  cancelados: number
}

/** Viaje de la moto entre dos puntos. */
export interface Tramo {
  t_salida: number
  t_llegada: number
  desde: number
  hasta: number
  clave: string
}

/** Evento de llegada a un punto. */
export interface Llegada {
  punto: number
  tipo: 'pickup' | 'dropoff'
}

/** Un frame = un minuto del turno. */
export interface Frame {
  t: number
  ofertas: Oferta[]
  decisiones: Decision[]
  llegada: Llegada | null
  cobro: number
  ganado: number
}

/** Un turno grabado completo. */
export interface TurnoData {
  meta: TurnoMeta
  config: ConfigTurno
  tramos: Tramo[]
  geometria: Record<string, [number, number][]>
  frames: Frame[]
}

/** Entrada del índice turnos.json. */
export interface TurnoIndexEntry {
  seed: number
  delta_pct: number
  greedy: TurnoMeta
  nuez: TurnoMeta
}

/** Índice de turnos grabados. */
export interface TurnoIndex {
  turnos: TurnoIndexEntry[]
}
