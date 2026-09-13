// Marcador compacto de los cinco agentes online del turno live. El mapa conserva
// solo Nuez vs Greedy: cinco rutas convertirían el demo en ruido visual.

import { useEffect, useState } from 'react'
import { RIVALES } from '../lib/resultsCopy'
import { esperarOracle, type LiveBenchmark, type LiveSnapshot } from '../lib/live'

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
export function benchmarkRows(
  snapshot: LiveSnapshot,
  oracleData?: { earnings: number; deliveries: number | null }
): BenchmarkRow[] {
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
      earnings: oracleData ? oracleData.earnings : RIVALES.media.Oracle,
      deliveries: oracleData ? oracleData.deliveries : null,
      kind: 'oracle',
    },
  ]
}

export function LiveBenchmarkRace({ snapshot }: { snapshot: LiveSnapshot }) {
  const [oracleData, setOracleData] = useState<{
    status: 'idle' | 'loading' | 'done' | 'failed'
    earnings: number
    deliveries: number | null
  }>({
    status: 'idle',
    earnings: RIVALES.media.Oracle,
    deliveries: null,
  })

  useEffect(() => {
    if (snapshot.status === 'ended' || snapshot.status === 'finished') {
      setOracleData((prev) => ({ ...prev, status: 'loading' }))
      let vigente = true
      esperarOracle(snapshot.session_id, () => vigente).then((res) => {
        if (!vigente || !res) return
        if (res.status === 'ready') {
          setOracleData({
            status: 'done',
            earnings: res.report.earnings_mxn,
            deliveries: res.report.deliveries,
          })
        } else {
          setOracleData((prev) => ({ ...prev, status: 'failed' }))
        }
      })
      return () => {
        vigente = false
      }
    } else {
      setOracleData({ status: 'idle', earnings: RIVALES.media.Oracle, deliveries: null })
    }
  }, [snapshot.status, snapshot.session_id])

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
        {benchmarkRows(snapshot, oracleData).map((row) => (
          <div className={`live-benchmark-row is-${row.kind}`} key={row.key}>
            <span className="live-benchmark-name">{row.label}</span>
            <span className="live-benchmark-detail">
              {row.kind === 'oracle' && oracleData.status === 'loading'
                ? 'computing...'
                : row.kind === 'oracle' && oracleData.status === 'done'
                ? `${row.deliveries} deliveries (computed)`
                : row.kind === 'oracle'
                ? 'waiting for shift end...'
                : row.deliveries === null
                ? 'offline average'
                : `${row.deliveries} deliveries`}
            </span>
            <strong className="live-benchmark-value num">
              {row.kind === 'oracle' && oracleData.status === 'loading' ? (
                <span className="loading-spinner" style={{ fontSize: '0.8em', opacity: 0.7 }}>...</span>
              ) : (
                `$${row.earnings.toFixed(0)}`
              )}
            </strong>
          </div>
        ))}
      </div>
      <p className="live-benchmark-note">
        Every live score is net of fuel for pickup, delivery, deadhead, and return. Oracle is the
        $259 reported offline average across 50 held-out shifts; it does not compete live.
      </p>
    </section>
  )
}
