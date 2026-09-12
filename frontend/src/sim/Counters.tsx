// Contadores lado a lado: ganancia, entregas, saltadas. Greedy vs Nuez.
// Colores con significado: esmeralda = dinero, ámbar = greedy, índigo = nuez.

import type { Contadores } from '../lib/sim'
import type { TurnoMeta } from '../lib/turno'

interface Props {
  greedy: Contadores
  nuez: Contadores
  greedyMeta: TurnoMeta
  nuezMeta: TurnoMeta
  terminado: boolean
}

export function Counters({ greedy, nuez, greedyMeta, nuezMeta, terminado }: Props) {
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
            {greedy.entregas} deliveries · {greedy.saltadas} skipped
          </span>
        </div>
        <div className="counter-agent">
          <span className="counter-agent-label is-nuez">Nuez</span>
          <span className="counter-value num">
            {nuez.ganado.toFixed(0)}
            <small>MXN</small>
          </span>
          <span className="counter-sub">
            {nuez.entregas} deliveries · {nuez.saltadas} skipped
          </span>
        </div>
      </div>

      {/* Diferencia */}
      <div className={`counter-diff ${diffClass}`}>
        {diff === 0 ? 'Tied' : `Nuez ${diffSign}MXN ${diff.toFixed(0)}`}
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
            <span>Nuez total</span>
            <strong className="num">{nuezMeta.ganado.toFixed(2)} MXN</strong>
          </div>
          <div className="turno-summary-row">
            <span>Late?</span>
            <strong>{nuezMeta.llego_tarde ? 'Yes' : 'No'}</strong>
          </div>
        </div>
      )}
    </div>
  )
}
