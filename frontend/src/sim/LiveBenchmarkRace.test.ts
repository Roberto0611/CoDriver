import { describe, expect, it } from 'vitest'

import { benchmarkRows } from './LiveBenchmarkRace'
import type { LiveSnapshot } from '../lib/live'

const snapshot = {
  nuez: { earnings_mxn: 260, deliveries: 5 },
  greedy: { earnings_mxn: 206, deliveries: 3 },
  benchmarks: {
    accept_all: { earnings_mxn: 182, deliveries: 3, skipped: 0, cancelled: 0 },
    highest_pay: { earnings_mxn: 133, deliveries: 2, skipped: 0, cancelled: 0 },
    nearest_first: { earnings_mxn: 129, deliveries: 2, skipped: 0, cancelled: 0 },
  },
} as LiveSnapshot

describe('LiveBenchmarkRace', () => {
  it('keeps all online policies in the live race and Oracle clearly offline', () => {
    expect(benchmarkRows(snapshot)).toMatchObject([
      { key: 'nuez', earnings: 260, kind: 'nuez' },
      { key: 'greedy', earnings: 206, kind: 'greedy' },
      { key: 'accept_all', earnings: 182, kind: 'baseline' },
      { key: 'highest_pay', earnings: 133, kind: 'baseline' },
      { key: 'nearest_first', earnings: 129, kind: 'baseline' },
      { key: 'oracle', earnings: 277.33, deliveries: null, kind: 'oracle' },
    ])
  })
})
