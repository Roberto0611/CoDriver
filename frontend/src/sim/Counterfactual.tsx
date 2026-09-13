// El reporte contrafactual al final del replay: renglones extra bajo el "Final Summary".
// Los datos salen de re-simular el turno (data/export_contrafactual.py), no de adivinar.
// Los saltos por reglas duras solo se cuentan: no tienen precio porque no se venden.
// Vehículo lleno va en su propio renglón: es un límite físico, no seguridad.

import { useEffect, useState } from 'react'
import {
  cargarContrafactual,
  formatoDelta,
  lineaDinero,
  lineaPedido,
  lineaSeguridad,
  type Contrafactual,
} from '../lib/contrafactual'
import '../styles/counterfactual.css'

interface Props {
  seed: number | null
  terminado: boolean
  /** Hora de arranque del turno, para nombrar cada pedido con hora de reloj. */
  horaInicio: number
}

interface ReportProps {
  datos: Contrafactual
  horaInicio: number
  /** The recorded replay can use the familiar title; live benchmarks must say what they are. */
  titulo?: string
  /** A live run may show a recorded reference rather than a calculation of that fresh run. */
  nota?: string
}

/** Shared report body for a recorded replay and the live shift's recorded reference. */
export function CounterfactualReport({
  datos,
  horaInicio,
  titulo = 'If Navie had taken its skips',
  nota = 'Each what-if re-runs the shift with one order.',
}: ReportProps) {
  const seguridad = lineaSeguridad(datos.safety_skips)

  return (
    <div className="turno-summary counterfactual">
      <span className="turno-summary-label">{titulo}</span>
      <p className="counterfactual-line">{lineaDinero(datos.money_skips)}</p>

      {datos.top.map((p) => (
        <div className="turno-summary-row" key={p.order_id}>
          <span>
            {lineaPedido(p, horaInicio)}
            {p.late ? ' · back late' : ''}
          </span>
          <strong className={`num counterfactual-delta ${p.delta_mxn > 0 ? 'is-gain' : 'is-loss'}`}>
            {formatoDelta(p.delta_mxn)}
          </strong>
        </div>
      ))}

      {seguridad && (
        <p className="counterfactual-line is-safety">
          <span className="counterfactual-lead">Blocked for safety, not for sale:</span> {seguridad}
        </p>
      )}

      {datos.capacity_skips > 0 && (
        <p className="counterfactual-line is-capacity">
          <span className="counterfactual-lead">Vehicle full:</span> {datos.capacity_skips}
        </p>
      )}

      <span className="counterfactual-note">{nota}</span>
    </div>
  )
}

export function Counterfactual({ seed, terminado, horaInicio }: Props) {
  // Se guarda junto con su seed: al cambiar de turno no se pinta el reporte del anterior.
  const [cargado, setCargado] = useState<{ seed: number; datos: Contrafactual | null } | null>(null)

  // Se pide al elegir el turno y otra vez al terminarlo: si la primera vez falló la red,
  // al llegar al final se reintenta. Lo que sí contestó sale del cache, sin otro fetch.
  useEffect(() => {
    if (seed == null) return
    let vigente = true
    cargarContrafactual(seed).then((datos) => {
      if (vigente) setCargado({ seed, datos })
    })
    return () => {
      vigente = false
    }
  }, [seed, terminado])

  const datos = cargado && cargado.seed === seed ? cargado.datos : null
  if (!terminado || !datos) return null

  return <CounterfactualReport datos={datos} horaInicio={horaInicio} />
}
