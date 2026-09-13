import { API_URL } from './api'

export type DecisionTimelineItem = {
  sim_time: string
  order_id: string
  decision: 'ACCEPT' | 'SKIP'
  reason: string
  binding_constraint: string | null
  net_pay_mxn: number
}

export type ShiftAnalytics = {
  source: 'tigerdata' | 'jsonl'
  log_path: string
  total_decisions: number
  accepted: number
  skipped: number
  accept_rate_pct: number
  by_constraint: Record<string, number>
  accepted_net_mxn: number
  timeline: DecisionTimelineItem[]
}

export async function getShiftAnalytics(signal?: AbortSignal): Promise<ShiftAnalytics> {
  const response = await fetch(`${API_URL}/analytics/shift`, { signal })
  if (!response.ok) throw new Error(`Analytics unavailable: ${response.status}`)
  return response.json() as Promise<ShiftAnalytics>
}
