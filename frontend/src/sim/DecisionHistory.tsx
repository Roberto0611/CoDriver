import { useEffect, useState } from 'react'
import { getShiftAnalytics, type ShiftAnalytics } from '../lib/analytics'

interface Props {
  lastDecisionId?: string
}

export function DecisionHistory({ lastDecisionId }: Props) {
  const [analytics, setAnalytics] = useState<ShiftAnalytics | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    void getShiftAnalytics(controller.signal)
      .then(setAnalytics)
      .catch((error: unknown) => {
        if ((error as Error).name !== 'AbortError') setError('History unavailable')
      })

    return () => controller.abort()
  }, [lastDecisionId])

  if (error) {
    return (
      <div className="decisions">
        <div className="decisions-title">DECISION HISTORY</div>
        <div className="decision-text" style={{ color: 'var(--rose-ink)' }}>
          {error}
        </div>
      </div>
    )
  }

  if (!analytics) {
    return null
  }

  const { source, accepted, skipped, accept_rate_pct, by_constraint, timeline } = analytics
  const latest = timeline.length > 0 ? timeline[0] : null

  return (
    <div className="decisions" style={{ paddingBottom: '8px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          position: 'sticky',
          top: 0,
          background: 'var(--card)',
          zIndex: 1,
          padding: '4px 0',
        }}
      >
        <div className="decisions-title" style={{ position: 'static', padding: 0 }}>
          DECISION HISTORY
        </div>
        <div className={`history-badge ${source === 'tigerdata' ? 'is-tigerdata' : 'is-jsonl'}`}>
          {source === 'tigerdata' ? 'TigerData' : 'Local replay'}
        </div>
      </div>

      <div style={{ fontSize: '12px', color: 'var(--ink-2)', marginBottom: '8px' }}>
        <strong>{accepted}</strong> accepted &middot; <strong>{skipped}</strong> skipped &middot;{' '}
        {accept_rate_pct.toFixed(0)}% acceptance
      </div>

      {Object.keys(by_constraint).length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <div
            style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink)', marginBottom: '4px' }}
          >
            Why Navie skipped orders
          </div>
          {Object.entries(by_constraint).map(([constraint, count]) => (
            <div
              key={constraint}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '12px',
                color: 'var(--ink-3)',
              }}
            >
              <span>
                {constraint === 'opportunity_cost'
                  ? 'Opportunity cost'
                  : constraint === 'heat_rule'
                    ? 'Heat rule'
                    : constraint === 'shift_end_infeasible'
                      ? 'Return-to-class deadline'
                      : constraint}
              </span>
              <span className="num" style={{ fontWeight: 600 }}>
                {count}
              </span>
            </div>
          ))}
        </div>
      )}

      {latest && (
        <div style={{ borderTop: '1px solid var(--surface-high)', paddingTop: '8px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink)' }}>
            Latest:{' '}
            <span
              style={{
                color: latest.decision === 'ACCEPT' ? 'var(--emerald-ink)' : 'var(--ink-3)',
              }}
            >
              {latest.decision}
            </span>{' '}
            &middot; <span className="num">{latest.order_id}</span>
          </div>
          <div
            style={{ fontSize: '12px', color: 'var(--ink-3)', marginTop: '2px', lineHeight: 1.4 }}
          >
            {latest.reason}
          </div>
        </div>
      )}
    </div>
  )
}
