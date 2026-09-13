export interface PracticeExpected {
  grade?: string
  category?: string
  expected_decision?: 'ACCEPT' | 'SKIP'
  expected_binding_constraint?: string
  expected_reason_mentions?: string[]
  service_min?: number
  state_precondition?: Record<string, number>
  state_neutral?: boolean
  note?: string
}

export interface PracticeActual {
  decision: 'ACCEPT' | 'SKIP' | null
  binding_constraint: string | null
  reason: string | null
  verdict: 'PASS' | 'FAIL' | 'ERROR' | null
  error: string | null
  graded_mode: 'carried' | 'override' | null
  sent_state: {
    continuous_riding_min?: number
    shift_elapsed_hours?: number
    in_flight_orders?: unknown[]
  } | null
}

export interface PracticeTest {
  order: {
    order_id: string
    sim_time: string
    zone_pickup_name?: string
    zone_dropoff_name?: string
    base_pay_mxn: number
    est_tip_mxn?: number
    surge_multiplier: number
    weight_kg: number
    volume_liters: number
    estimated_pickup_min?: number
    estimated_delivery_min?: number
  }
  minute: number
  expected: PracticeExpected
  actual: PracticeActual | null
}

export interface PracticeReplay {
  kind: 'courier_practice_pack_replay'
  pack_id: string
  title: string
  manifest: {
    shift_start_time: string
    shift_end_time: string
    vehicle: string
  }
  duration_min: number
  summary: {
    tests: number
    passed: number
    failed: number
    source: string
  }
  tests: PracticeTest[]
}

export async function cargarPracticePack(): Promise<PracticeReplay> {
  const respuesta = await fetch('/courier_practice_pack_replay.json')
  if (!respuesta.ok) throw new Error('Safety Lab replay is unavailable.')
  return respuesta.json() as Promise<PracticeReplay>
}

export function horaDelPack(startTime: string, minute: number): string {
  const inicio = new Date(startTime)
  const reloj = new Date(inicio.getTime() + minute * 60_000)
  return `${String(reloj.getHours()).padStart(2, '0')}:${String(reloj.getMinutes()).padStart(2, '0')}`
}

export function etiquetaRestriccion(value: string | null | undefined): string {
  if (!value) return 'No binding constraint'
  return value.replaceAll('_', ' ')
}
