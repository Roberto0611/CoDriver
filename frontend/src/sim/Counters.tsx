// Contadores lado a lado: ganancia, entregas, saltadas. Greedy vs Nuez.
// Colores con significado: esmeralda = dinero, ámbar = greedy, índigo = nuez.

import { entregasTexto, horaDeRegreso, type ConfigRegreso } from '../lib/countersCopy'
import type { Contadores } from '../lib/sim'
import type { TurnoMeta } from '../lib/turno'

interface Props {
  greedy: Contadores
  nuez: Contadores
  greedyMeta: TurnoMeta
  nuezMeta: TurnoMeta
  terminado: boolean
  /**
   * El config del turno, para decir a qué hora hay que volver. Opcional para que
   * /live siga compilando sin tocarlo: sin config no se inventa una hora, se dice
   * solo en qué minuto volvió.
   */
  config?: ConfigRegreso
}

export function Counters({ greedy, nuez, greedyMeta, nuezMeta, terminado, config }: Props) {
  const diff = nuez.ganado - greedy.ganado
  const diffClass = diff > 0 ? 'is-positive' : diff < 0 ? 'is-negative' : 'is-neutral'
  const diffSign = diff > 0 ? '+' : ''

  return (
    <div className="counters">
      <div className="counters-title">Earnings</div>

      {/* Ganancia */}
      <div className="counter-row">
        <div className="counter-agent">
          <span className="counter-agent-label is-greedy">Greedy</span>
          <span className="counter-value num">
            {greedy.ganado.toFixed(0)}
            <small>MXN</small>
          </span>
          <span className="counter-sub">
            {entregasTexto(greedy.entregas)} · {greedy.saltadas} skipped
          </span>
        </div>
        <div className="counter-agent">
          <span className="counter-agent-label is-nuez">Navie</span>
          <span className="counter-value num">
            {nuez.ganado.toFixed(0)}
            <small>MXN</small>
          </span>
          <span className="counter-sub">
            {entregasTexto(nuez.entregas)} · {nuez.saltadas} skipped
          </span>
        </div>
      </div>

      {/* Diferencia */}
      <div className={`counter-diff ${diffClass}`}>
        {diff === 0 ? 'Tied' : `Navie ${diffSign}MXN ${diff.toFixed(0)}`}
      </div>

      {/* Resumen final */}
      {terminado && (
        <div className="turno-summary">
          <span className="turno-summary-label">Final Summary</span>
          <div className="turno-summary-row">
            <span>Greedy total</span>
            <strong className="num">{greedyMeta.ganado.toFixed(2)} MXN</strong>
          </div>
          <div className="turno-summary-row">
            <span>Navie total</span>
            <strong className="num">{nuezMeta.ganado.toFixed(2)} MXN</strong>
          </div>
          <div className="turno-summary-row">
            <span>Safety violations</span>
            <strong>{nuezMeta.violaciones ?? 0}</strong>
          </div>
          <div className="turno-summary-row">
            <span>{config ? `Back by ${horaDeRegreso(config)}` : 'Back at anchor'}</span>
            <strong>
              {nuezMeta.regreso_en?.toFixed(1) ?? '?'} min {nuezMeta.llego_tarde ? '✗' : '✓'}
            </strong>
          </div>
          {(nuezMeta.cancelados ?? 0) > 0 && (
            <div className="turno-summary-row" style={{ color: '#f43f5e', fontWeight: 600 }}>
              <span>Orders canceled due to disruption</span>
              <strong>{nuezMeta.cancelados}</strong>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
