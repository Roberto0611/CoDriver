// Marcador compacto de los cinco agentes online del turno live. El mapa conserva
// solo Nuez vs Greedy: cinco rutas convertirían el demo en ruido visual.

import { RIVALES } from '../lib/resultsCopy'
import type { LiveBenchmark, LiveSnapshot } from '../lib/live'

export interface BenchmarkRow {
  key: string
  label: string
  earnings: number
  deliveries: number | null
  kind: 'nuez' | 'greedy' | 'baseline' | 'oracle'
}

const ETIQUETAS = {
  accept_all: 'AcceptAll',
  highest_pay: 'HighestPay',
  nearest_first: 'NearestFirst',
} as const

function fila(key: keyof typeof ETIQUETAS, data: LiveBenchmark): BenchmarkRow {
  return {
    key,
    label: ETIQUETAS[key],
    earnings: data.earnings_mxn,
    deliveries: data.deliveries,
    kind: 'baseline',
  }
}

/** Exportado para que el orden del pitch no dependa de cómo venga el objeto HTTP. */
export function benchmarkRows(snapshot: LiveSnapshot): BenchmarkRow[] {
  return [
    {
      key: 'nuez',
      label: 'Navie',
      earnings: snapshot.nuez.earnings_mxn,
      deliveries: snapshot.nuez.deliveries,
      kind: 'nuez',
    },
    {
      key: 'greedy',
      label: 'GreedyRate',
      earnings: snapshot.greedy.earnings_mxn,
      deliveries: snapshot.greedy.deliveries,
      kind: 'greedy',
    },
    fila('accept_all', snapshot.benchmarks.accept_all),
    fila('highest_pay', snapshot.benchmarks.highest_pay),
    fila('nearest_first', snapshot.benchmarks.nearest_first),
    {
      key: 'oracle',
      label: 'Oracle',
      earnings: RIVALES.media.Oracle,
      deliveries: null,
      kind: 'oracle',
    },
  ]
}

export function LiveBenchmarkRace({ snapshot }: { snapshot: LiveSnapshot }) {
  return (
    <section className="live-benchmark-race" aria-label="Live benchmark race">
      <div className="live-benchmark-head">
        <div>
          <span className="caps">Live benchmark race</span>
          <p>Same offers and disruptions for every online policy.</p>
        </div>
        <span className="live-benchmark-live">LIVE</span>
      </div>
      <div className="live-benchmark-rows">
        {benchmarkRows(snapshot).map((row) => (
          <div className={`live-benchmark-row is-${row.kind}`} key={row.key}>
            <span className="live-benchmark-name">{row.label}</span>
            <span className="live-benchmark-detail">
              {row.deliveries === null ? 'offline average' : `${row.deliveries} deliveries`}
            </span>
            <strong className="live-benchmark-value num">${row.earnings.toFixed(0)}</strong>
          </div>
        ))}
      </div>
      <p className="live-benchmark-note">
        Oracle is the $277 offline average across 50 held-out shifts; it sees the entire shift in
        advance and does not compete live.
      </p>
    </section>
  )
}
