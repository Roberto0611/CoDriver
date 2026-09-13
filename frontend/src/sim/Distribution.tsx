// Panel de evidencia junto al turno animado: un turno no prueba nada, estos sí.
// Cada número dice de cuántos turnos y de qué seeds sale; los valores viven en
// lib/resultsCopy.ts con el comando que los produjo.

import { useState } from 'react'
import {
  DELTA_200,
  HISTOGRAMA,
  RIVALES,
  SEEDS_TUNEO,
  porcentajeDelOracle,
} from '../lib/resultsCopy'
import { Icon } from '../ui/icons'

const rango = ([desde, hasta]: readonly [number, number]) => `${desde}–${hasta}`
const pesos = (mxn: number) => `$${Math.round(mxn)}`
const delta = (pct: number) => `+${pct.toFixed(1)}%`

interface Props {
  /** Solo para pruebas y capturas: el panel arranca cerrado en la app. */
  abierto?: boolean
}

export function Distribution({ abierto = false }: Props) {
  const [expanded, setExpanded] = useState(abierto)
  const { media } = RIVALES

  return (
    <div className="glass-card distribution-panel">
      <div
        className="distribution-header"
        onClick={() => setExpanded(!expanded)}
        style={{
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span
          className="distribution-title"
          style={{ fontWeight: 600, fontSize: '0.95rem', color: '#0f172a' }}
        >
          Simulated Distribution
        </span>
        <span
          style={{
            color: '#64748b',
            display: 'flex',
            alignItems: 'center',
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
          }}
        >
          {Icon.chevron}
        </span>
      </div>

      {expanded && (
        <div className="distribution-content" style={{ marginTop: '12px' }}>
          <p
            style={{ fontSize: '0.85rem', color: '#475569', marginBottom: '12px', lineHeight: 1.4 }}
          >
            A single shift can be lucky or unlucky. Over {DELTA_200.turnos} held-out shifts (REPORTE{' '}
            {rango(DELTA_200.seedsReporte)}), Navie out-earns Greedy by{' '}
            <strong>{delta(DELTA_200.normal.deltaPct)}</strong> on normal days (wins{' '}
            {DELTA_200.normal.gana}/{DELTA_200.turnos}) and{' '}
            <strong>{delta(DELTA_200.shocks.deltaPct)}</strong> with disruptions (wins{' '}
            {DELTA_200.shocks.gana}/{DELTA_200.turnos}).
          </p>
          <p style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '6px' }}>
            Mean earnings, {RIVALES.turnos} held-out shifts (REPORTE {rango(RIVALES.seedsReporte)})
            · {RIVALES.config.duracionMin} min, {RIVALES.config.vehiculo},{' '}
            {String(RIVALES.config.horaInicio).padStart(2, '0')}:00
          </p>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '8px',
              fontSize: '0.8rem',
              backgroundColor: '#f8fafc',
              padding: '10px',
              borderRadius: '6px',
              marginBottom: '12px',
              border: '1px solid #e2e8f0',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>AcceptAll</span>{' '}
              <strong style={{ color: '#64748b' }}>{pesos(media.AcceptAll)}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>GreedyRate</span>{' '}
              <strong style={{ color: '#f59e0b' }}>{pesos(media.GreedyRate)}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>HighestPay</span>{' '}
              <strong style={{ color: '#64748b' }}>{pesos(media.HighestPay)}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>OurAgent</span>{' '}
              <strong style={{ color: '#4f46e5' }}>{pesos(media.OurAgent)}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>NearestFirst</span>{' '}
              <strong style={{ color: '#64748b' }}>{pesos(media.NearestFirst)}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Oracle</span>{' '}
              <strong style={{ color: '#10b981' }}>{pesos(media.Oracle)}</strong>
            </div>
          </div>
          <p
            style={{
              fontSize: '0.75rem',
              color: '#64748b',
              fontStyle: 'italic',
              marginBottom: '8px',
            }}
          >
            * Oracle sees the whole shift in advance and keeps the best of a beam search and the
            five online policies: our best-known offline plan, not a proven optimum. Navie reaches{' '}
            {porcentajeDelOracle()}% of it. Tuned on TUNEO {rango(SEEDS_TUNEO)}, never reported on.
          </p>
          <img
            src="/distribucion_ganancias.png"
            alt={`Earnings per shift, Greedy vs Navie, ${HISTOGRAMA.turnos} REPORTE shifts`}
            style={{ width: '100%', borderRadius: '4px', border: '1px solid #e2e8f0' }}
          />
          <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '6px' }}>
            Histogram from an earlier engine build on the same {HISTOGRAMA.turnos} seeds (means MXN{' '}
            {HISTOGRAMA.media.greedy} and {HISTOGRAMA.media.navie}); the figures above are current.
          </p>
        </div>
      )}
    </div>
  )
}
