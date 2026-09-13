import { useState } from 'react'
import { Icon } from '../ui/icons'

export function Distribution() {
  const [expanded, setExpanded] = useState(false)

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
          Simulated Distribution (200 shifts)
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
            A single shift can be lucky or unlucky. Over 200 shifts, Navie consistently outperforms
            Greedy by <strong>+33.5%</strong> on normal days, and <strong>+32.9%</strong> on days
            with disruptions.
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
              <span>AcceptAll</span> <strong style={{ color: '#64748b' }}>$180</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>GreedyRate</span> <strong style={{ color: '#f59e0b' }}>$206</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>HighestPay</span> <strong style={{ color: '#64748b' }}>$133</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>OurAgent</span> <strong style={{ color: '#4f46e5' }}>$265</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>NearestFirst</span> <strong style={{ color: '#64748b' }}>$128</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Oracle</span> <strong style={{ color: '#10b981' }}>$281</strong>
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
            * Oracle knows the entire shift in advance. Navie achieves 94% of the theoretical
            optimum.
          </p>
          <img
            src="/distribucion_ganancias.png"
            alt="Distribución de Ganancias"
            style={{ width: '100%', borderRadius: '4px', border: '1px solid #e2e8f0' }}
          />
        </div>
      )}
    </div>
  )
}
