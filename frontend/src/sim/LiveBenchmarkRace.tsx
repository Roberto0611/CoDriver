// Marcador compacto de los cinco agentes online del turno live. El mapa conserva
// solo Nuez vs Greedy: cinco rutas convertirían el demo en ruido visual.

import { useEffect, useState } from 'react'

import {
  esperarOracle,
  type LiveBenchmark,
  type LiveOracleState,
  type LiveSnapshot,
} from '../lib/live'

export interface BenchmarkRow {
  key: string
  label: string
  earnings: number | null
  deliveries: number | null
  detail: string
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
    detail: `${data.deliveries} deliveries`,
    kind: 'baseline',
  }
}

/** Exportado para que el orden del pitch no dependa de cómo venga el objeto HTTP. */
export function benchmarkRows(
  snapshot: LiveSnapshot,
  oracle: LiveOracleState = { status: 'idle' }
): BenchmarkRow[] {
  const oracleRow: BenchmarkRow =
    oracle.status === 'ready'
      ? {
          key: 'oracle',
          label: 'Oracle',
          earnings: oracle.report.earnings_mxn,
          deliveries: oracle.report.deliveries,
          detail: `${oracle.report.source} · hindsight`,
          kind: 'oracle',
        }
      : {
          key: 'oracle',
          label: 'Oracle',
          earnings: null,
          deliveries: null,
          detail:
            oracle.status === 'computing'
              ? 'computing hindsight...'
              : oracle.status === 'failed'
                ? 'unavailable'
                : 'waiting for shift end...',
          kind: 'oracle',
        }
  return [
    {
      key: 'nuez',
      label: 'Navie',
      earnings: snapshot.nuez.earnings_mxn,
      deliveries: snapshot.nuez.deliveries,
      detail: `${snapshot.nuez.deliveries} deliveries`,
      kind: 'nuez',
    },
    {
      key: 'greedy',
      label: 'GreedyRate',
      earnings: snapshot.greedy.earnings_mxn,
      deliveries: snapshot.greedy.deliveries,
      detail: `${snapshot.greedy.deliveries} deliveries`,
      kind: 'greedy',
    },
    fila('accept_all', snapshot.benchmarks.accept_all),
    fila('highest_pay', snapshot.benchmarks.highest_pay),
    fila('nearest_first', snapshot.benchmarks.nearest_first),
    oracleRow,
  ]
}

export function LiveBenchmarkRace({ snapshot }: { snapshot: LiveSnapshot }) {
  const [oracle, setOracle] = useState<LiveOracleState>({ status: 'idle' })

  useEffect(() => {
    let cancelado = false
    if (snapshot.status === 'running') {
      setOracle({ status: 'idle' })
      return () => {
        cancelado = true
      }
    }
    setOracle({ status: 'computing' })
    void esperarOracle(snapshot.session_id, () => !cancelado).then((final) => {
      if (final && !cancelado) setOracle(final)
    })
    return () => {
      cancelado = true
    }
  }, [snapshot.session_id, snapshot.status])

  return (
    <section className="live-benchmark-race" aria-label="Live benchmark race">
      <div className="live-benchmark-head">
        <div>
          <span className="caps">Live benchmark race</span>
          <p>Same offers, disruptions, and all-km fuel cost for every online policy.</p>
        </div>
        <span className="live-benchmark-live">LIVE</span>
      </div>
      <div className="live-benchmark-rows">
        {benchmarkRows(snapshot, oracle).map((row) => (
          <div className={`live-benchmark-row is-${row.kind}`} key={row.key}>
            <span className="live-benchmark-name">{row.label}</span>
            <span className="live-benchmark-detail">{row.detail}</span>
            <strong className="live-benchmark-value num">
              {row.earnings === null ? '—' : `$${row.earnings.toFixed(0)}`}
            </strong>
          </div>
        ))}
      </div>
      <p className="live-benchmark-note">
        Every online score is net of fuel for pickup, delivery, deadhead, and return. Oracle appears
        only after shift end: it sees the completed shift and is not part of the live decision path.
      </p>
    </section>
  )
}
