import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  cargarPracticePack,
  etiquetaRestriccion,
  horaDelPack,
  type PracticeReplay,
  type PracticeTest,
} from './lib/practice-pack'
import { Icon } from './ui/icons'

const MS_PER_EVENT = 1100

function decisionClass(decision: string | null | undefined): string {
  return decision === 'ACCEPT' ? 'is-accept' : 'is-skip'
}

function DecisionMark({ decision }: { decision: string | null | undefined }) {
  return (
    <span className={`lab-decision-mark ${decisionClass(decision)}`}>
      {decision === 'ACCEPT' ? Icon.accept : Icon.skip}
    </span>
  )
}

function TestDetail({ test, startTime }: { test: PracticeTest; startTime: string }) {
  const actual = test.actual
  const order = test.order
  const state = actual?.sent_state
  const pickup = order.zone_pickup_name ?? 'Local pickup zone'
  const dropoff = order.zone_dropoff_name ?? 'Marked zone'
  const pay = order.base_pay_mxn * order.surge_multiplier + (order.est_tip_mxn ?? 0)

  return (
    <section className="lab-detail" aria-live="polite">
      <div className="lab-detail-heading">
        <div>
          <p className="caps">Selected probe</p>
          <h2>{order.order_id}</h2>
        </div>
        <time className="lab-clock num">{horaDelPack(startTime, test.minute)}</time>
      </div>

      <p className="lab-note">{test.expected.note}</p>

      <dl className="lab-order-facts">
        <div>
          <dt>Route</dt>
          <dd>
            {pickup} to {dropoff}
          </dd>
        </div>
        <div>
          <dt>Offer</dt>
          <dd className="num">MXN {pay.toFixed(0)}</dd>
        </div>
        <div>
          <dt>Load</dt>
          <dd className="num">
            {order.weight_kg} kg · {order.volume_liters} L
          </dd>
        </div>
        <div>
          <dt>Declared service</dt>
          <dd className="num">{test.expected.service_min ?? '—'} min</dd>
        </div>
      </dl>

      <div className="lab-verdict-grid">
        <div className="lab-verdict-column">
          <p className="caps">Expected</p>
          <div className="lab-decision-line">
            <DecisionMark decision={test.expected.expected_decision} />
            <strong>{test.expected.expected_decision ?? 'CONSISTENCY'}</strong>
          </div>
          <p className="lab-constraint">
            {etiquetaRestriccion(test.expected.expected_binding_constraint)}
          </p>
        </div>
        <div className="lab-verdict-column">
          <p className="caps">Observed</p>
          <div className="lab-decision-line">
            <DecisionMark decision={actual?.decision} />
            <strong>{actual?.decision ?? 'Not run'}</strong>
            {actual?.verdict && <span className="lab-verdict">{actual.verdict}</span>}
          </div>
          <p className="lab-constraint">{etiquetaRestriccion(actual?.binding_constraint)}</p>
        </div>
      </div>

      <div className="lab-state">
        <p className="caps">State supplied to Nuez</p>
        <div className="lab-state-values num">
          <span>{state?.continuous_riding_min ?? 0} min continuous riding</span>
          <span>{state?.in_flight_orders?.length ?? 0} orders in flight</span>
          <span>{actual?.graded_mode ?? 'expected'} state</span>
        </div>
      </div>

      {actual?.reason && <blockquote className="lab-reason">“{actual.reason}”</blockquote>}
      {actual?.error && <p className="lab-error">{actual.error}</p>}
    </section>
  )
}

export default function SafetyLabView() {
  const [replay, setReplay] = useState<PracticeReplay | null>(null)
  const [selected, setSelected] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    cargarPracticePack()
      .then((data) => {
        setReplay(data)
        setSelected(Math.min(3, data.tests.length - 1))
      })
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : 'Could not load Safety Lab.')
      )
  }, [])

  useEffect(() => {
    if (!isPlaying || !replay) return
    const timer = window.setInterval(() => {
      setSelected((current) => {
        if (current >= replay.tests.length - 1) {
          setIsPlaying(false)
          return current
        }
        return current + 1
      })
    }, MS_PER_EVENT)
    return () => window.clearInterval(timer)
  }, [isPlaying, replay])

  if (error) {
    return (
      <main className="safety-lab safety-lab-center">
        <p className="caps">Safety Lab</p>
        <h1>Replay unavailable</h1>
        <p>{error}</p>
        <Link to="/sim" className="lab-back-link">
          Back to recorded shifts
        </Link>
      </main>
    )
  }

  if (!replay) {
    return (
      <main className="safety-lab safety-lab-center">
        <p className="caps">Safety Lab</p>
        <h1>Loading the practice shift…</h1>
      </main>
    )
  }

  const test = replay.tests[selected]
  const go = (delta: number) =>
    setSelected((current) => Math.max(0, Math.min(replay.tests.length - 1, current + delta)))

  return (
    <main className="safety-lab">
      <header className="lab-header">
        <Link className="lab-brand" to="/sim" aria-label="Back to recorded shifts">
          {Icon.mark}
          <span>Nuez</span>
        </Link>
        <div className="lab-header-title">
          <p className="caps">Courier practice pack</p>
          <h1>Safety Lab</h1>
        </div>
        <div className="lab-shift-meta num">
          <span>14:00–22:30</span>
          <span>8.5 h · moto</span>
        </div>
      </header>

      <section className="lab-summary" aria-label="Practice pack summary">
        <div>
          <span className="caps">Probes</span>
          <strong className="num">{replay.summary.tests}</strong>
        </div>
        <div>
          <span className="caps">Passed</span>
          <strong className="num">{replay.summary.passed}</strong>
        </div>
        <div>
          <span className="caps">Needs work</span>
          <strong className="num">{replay.summary.failed}</strong>
        </div>
        <p>Each point is one decision under a real shift state — not an isolated API call.</p>
      </section>

      <section className="lab-timeline" aria-label="Practice shift timeline">
        <div className="lab-timeline-topline">
          <p className="caps">8.5-hour shift</p>
          <span className="num">{horaDelPack(replay.manifest.shift_start_time, test.minute)}</span>
        </div>
        <div className="lab-track">
          {replay.tests.map((item, index) => (
            <button
              key={item.order.order_id}
              className={`lab-event at-${item.minute} ${index === selected ? 'is-selected' : ''} ${item.actual?.verdict === 'PASS' ? 'is-pass' : 'is-needs-work'}`}
              onClick={() => {
                setSelected(index)
                setIsPlaying(false)
              }}
              aria-label={`${item.order.order_id} at ${horaDelPack(replay.manifest.shift_start_time, item.minute)}`}
              title={`${item.order.order_id} · ${horaDelPack(replay.manifest.shift_start_time, item.minute)}`}
            />
          ))}
        </div>
        <div className="lab-timeline-labels num">
          <span>14:00</span>
          <span>22:30</span>
        </div>
        <div className="lab-controls">
          <button
            className="lab-control"
            onClick={() => go(-1)}
            disabled={selected === 0}
            aria-label="Previous probe"
          >
            {Icon.stepBack}
          </button>
          <button
            className="lab-control lab-control-main"
            onClick={() => setIsPlaying((value) => !value)}
            aria-label={isPlaying ? 'Pause probes' : 'Play probes'}
          >
            {isPlaying ? Icon.pause : Icon.play}
          </button>
          <button
            className="lab-control"
            onClick={() => go(1)}
            disabled={selected === replay.tests.length - 1}
            aria-label="Next probe"
          >
            {Icon.stepForward}
          </button>
          <span className="lab-probe-count num">
            Probe {selected + 1} / {replay.tests.length}
          </span>
        </div>
      </section>

      <TestDetail test={test} startTime={replay.manifest.shift_start_time} />

      <nav className="lab-probe-list" aria-label="Practice probes">
        {replay.tests.map((item, index) => (
          <button
            key={item.order.order_id}
            className={`lab-probe-button ${index === selected ? 'is-selected' : ''}`}
            onClick={() => {
              setSelected(index)
              setIsPlaying(false)
            }}
          >
            <span className="num">
              {horaDelPack(replay.manifest.shift_start_time, item.minute)}
            </span>
            <span>{item.order.order_id}</span>
            <span>{etiquetaRestriccion(item.expected.expected_binding_constraint)}</span>
          </button>
        ))}
      </nav>
    </main>
  )
}
