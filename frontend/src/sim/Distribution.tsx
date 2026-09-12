import { useState } from 'react'
import { Icon } from '../ui/icons'

export function Distribution() {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="glass-card distribution-panel">
      <div 
        className="distribution-header" 
        onClick={() => setExpanded(!expanded)}
        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
      >
        <span className="distribution-title" style={{ fontWeight: 600, fontSize: '0.95rem', color: '#0f172a' }}>
          Simulated Distribution (200 shifts)
        </span>
        <span style={{ color: '#64748b', display: 'flex', alignItems: 'center', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>
          {Icon.chevron}
        </span>
      </div>
      
      {expanded && (
        <div className="distribution-content" style={{ marginTop: '12px' }}>
          <p style={{ fontSize: '0.85rem', color: '#475569', marginBottom: '8px', lineHeight: 1.4 }}>
            A single shift can be lucky or unlucky. Over 200 shifts, Nuez consistently outperforms Greedy by +29.2%.
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
