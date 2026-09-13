// El reporte contrafactual del turno grabado: ¿y si Nuez hubiera tomado lo que saltó?
// Lo graba data/export_contrafactual.py en frontend/public/contrafactual_<seed>.json.
// Cada salto por dinero se re-simula SOLO; los deltas no se suman, y la UI no los suma.

import type { Restriccion } from '../contract'
import { etiquetaRestriccion } from './decision-text'
import { minutosAHora } from './sim'

/** Un pedido saltado por dinero, re-simulado aceptándolo en ese momento. */
export interface PedidoContrafactual {
  order_id: string
  minute: number
  net_pay_mxn: number
  minutes: number
  time_value_mxn: number
  delta_mxn: number
  forced_earned_mxn: number
  forced_deliveries: number
  late: boolean
  cancelled: number
}

export interface SaltosPorDinero {
  count: number
  evaluated: number
  infeasible: number
  would_earn_less: number
  would_earn_more: number
  no_change: number
  late_runs: number
  cancelled_runs: number
  avg_delta_mxn: number | null
  max_gain_mxn: number | null
  max_loss_mxn: number | null
}

export interface Contrafactual {
  seed: number
  policy: string
  actual: { earned_mxn: number; deliveries: number; offers: number; late: boolean }
  skipped_total: number
  money_skips: SaltosPorDinero
  /** Solo seguridad. La capacidad va aparte: un vehículo lleno no es un riesgo. */
  safety_skips: Partial<
    Record<Exclude<Restriccion, 'reservation_wage' | 'vehicle_capacity'>, number>
  >
  capacity_skips: number
  top: PedidoContrafactual[]
  note: string
}

const _cache = new Map<number, Contrafactual | null>()

/** Revisión mínima de forma: el dev server puede contestar index.html con 200. */
export function esContrafactual(x: unknown): x is Contrafactual {
  if (typeof x !== 'object' || x === null) return false
  const c = x as Record<string, unknown>
  return (
    typeof c.seed === 'number' &&
    typeof c.money_skips === 'object' &&
    c.money_skips !== null &&
    typeof c.safety_skips === 'object' &&
    c.safety_skips !== null &&
    typeof c.capacity_skips === 'number' &&
    Array.isArray(c.top)
  )
}

/**
 * Carga el contrafactual de un seed. null si no existe o no se puede leer.
 * Solo se recuerda lo que el servidor contestó: un tropiezo de red (el dev server
 * reiniciando) no deja el reporte escondido hasta recargar la página.
 */
export async function cargarContrafactual(seed: number): Promise<Contrafactual | null> {
  if (_cache.has(seed)) return _cache.get(seed) ?? null
  let res: Response
  try {
    res = await fetch(`/contrafactual_${seed}.json`)
  } catch {
    return null
  }
  let datos: Contrafactual | null = null
  if (res.ok) {
    const crudo: unknown = await res.json().catch(() => null)
    datos = esContrafactual(crudo) && crudo.seed === seed ? crudo : null
  }
  _cache.set(seed, datos)
  return datos
}

/** Pesos sin centavos con signo tipográfico: "+MXN 35", "−MXN 42", "MXN 0". */
export function formatoDelta(delta: number): string {
  const redondo = Math.round(delta)
  if (redondo === 0) return 'MXN 0'
  return `${redondo > 0 ? '+' : '−'}MXN ${Math.abs(redondo)}`
}

/** La frase de los saltos por dinero. Nunca da un total: cada corrida es aparte. */
export function lineaDinero(m: SaltosPorDinero): string {
  if (m.count === 0) return 'Skipped nothing for money.'
  const partes = [`Skipped ${m.count} for money.`]
  if (m.evaluated === 1) {
    const d = Math.round(m.max_gain_mxn ?? m.max_loss_mxn ?? 0)
    const cambio = d === 0 ? 'the same' : `MXN ${Math.abs(d)} ${d > 0 ? 'more' : 'less'}`
    partes.push(`Taking it would have earned ${cambio}.`)
  } else if (m.evaluated > 1) {
    const mejor = m.max_gain_mxn != null ? ` (best ${formatoDelta(m.max_gain_mxn)})` : ''
    partes.push(
      `Taking any single one: ${m.would_earn_less} would have earned less, ` +
        `${m.would_earn_more} more${mejor}.`
    )
  }
  if (m.infeasible > 0) partes.push(`${m.infeasible} still blocked by a hard rule when forced.`)
  return partes.join(' ')
}

/** "Heat rule 23 · Shift ends 23": solo las restricciones que sí mordieron. */
export function lineaSeguridad(saltos: Contrafactual['safety_skips']): string {
  return Object.entries(saltos)
    .filter(([, n]) => (n ?? 0) > 0)
    .map(([r, n]) => `${etiquetaRestriccion(r as Restriccion)} ${n}`)
    .join(' · ')
}

/**
 * La etiqueta de un pedido: "14:48 · MXN 42 for 22 min". Con la hora de reloj, igual
 * que el timeline y el panel de decisiones, para poder encontrarlo ahí.
 */
export function lineaPedido(p: PedidoContrafactual, horaInicio: number): string {
  const hora = minutosAHora(horaInicio, p.minute)
  return `${hora} · MXN ${Math.round(p.net_pay_mxn)} for ${Math.round(p.minutes)} min`
}
