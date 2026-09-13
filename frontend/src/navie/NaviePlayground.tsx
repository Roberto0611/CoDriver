import { useState } from 'react'
import { NavieCompass, type CompassMode } from './NavieCompass'

const modes: CompassMode[] = ['idle', 'wink', 'happy', 'searching', 'error', 'logo']

export function NaviePlayground() {
  const [mode, setMode] = useState<CompassMode>('idle')

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: 40,
        gap: 20,
      }}
    >
      <h1 style={{ margin: 0, fontSize: 32 }}>Navie playground</h1>

      <NavieCompass mode={mode} />

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
        {modes.map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              border: 'none',
              background: mode === m ? '#684959' : '#1a1a1a',
              color: '#fff',
              padding: '9px 16px',
              borderRadius: 20,
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
              opacity: mode === m ? 1 : 0.8,
              textTransform: 'capitalize',
            }}
          >
            {m}
          </button>
        ))}
      </div>
    </div>
  )
}
