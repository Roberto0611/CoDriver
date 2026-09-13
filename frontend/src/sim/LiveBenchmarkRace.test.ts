import { describe, expect, it } from 'vitest'

import { benchmarkRows } from './LiveBenchmarkRace'
import type { LiveSnapshot } from '../lib/live'

const snapshot = {
  nuez: { earnings_mxn: 260, gross_earnings_mxn: 290, fuel_cost_mxn: 30, deliveries: 5 },
  greedy: { earnings_mxn: 206, gross_earnings_mxn: 250, fuel_cost_mxn: 44, deliveries: 3 },
  benchmarks: {
    accept_all: {
      earnings_mxn: 182,
      gross_earnings_mxn: 210,
      fuel_cost_mxn: 28,
      deliveries: 3,
      skipped: 0,
      cancelled: 0,
    },
    highest_pay: {
      earnings_mxn: 133,
      gross_earnings_mxn: 150,
      fuel_cost_mxn: 17,
      deliveries: 2,
      skipped: 0,
      cancelled: 0,
    },
    nearest_first: {
      earnings_mxn: 129,
      gross_earnings_mxn: 149,
      fuel_cost_mxn: 20,
      deliveries: 2,
      skipped: 0,
      cancelled: 0,
    },
  },
} as LiveSnapshot

describe('LiveBenchmarkRace', () => {
  it('keeps online policies in the live race and waits for the offline Oracle', () => {
    expect(benchmarkRows(snapshot)).toMatchObject([
      { key: 'nuez', earnings: 260, kind: 'nuez' },
      { key: 'greedy', earnings: 206, kind: 'greedy' },
      { key: 'accept_all', earnings: 182, kind: 'baseline' },
      { key: 'highest_pay', earnings: 133, kind: 'baseline' },
      { key: 'nearest_first', earnings: 129, kind: 'baseline' },
      {
        key: 'oracle',
        earnings: null,
        deliveries: null,
        detail: 'waiting for shift end...',
        kind: 'oracle',
      },
    ])
  })

  it('labels the completed-shift source instead of pretending Oracle made the live decisions', () => {
    expect(
      benchmarkRows(snapshot, {
        status: 'ready',
        report: {
          session_id: 'live-1',
          seed: 2000,
          earnings_mxn: 281,
          gross_earnings_mxn: 310,
          fuel_cost_mxn: 29,
          deliveries: 6,
          source: 'AgendaOracle',
        },
      })
    ).toMatchObject([
      {},
      {},
      {},
      {},
      {},
      { key: 'oracle', earnings: 281, detail: 'AgendaOracle · hindsight', kind: 'oracle' },
    ])
  })
})
