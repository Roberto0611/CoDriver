// Seccion de hallazgos del landing: encabezado y dos columnas (Navie animado + tarjeta
// con los puntos tecnicos y los botones al mapa).

import { Link } from 'react-router-dom'
import NavieBackgroundPanel from '../NavieBackgroundPanel'

export function LandingFindings() {
  return (
    <section
      style={{
        width: '100%',
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '54px 20px 80px 20px',
        boxSizing: 'border-box',
      }}
    >
      {/* Encabezado de la sección de hallazgos */}
      <div style={{ marginBottom: '32px', textAlign: 'left' }}>
        <h2
          style={{
            fontSize: 'clamp(1.8rem, 3.2vw, 2.4rem)',
            fontWeight: 800,
            color: 'var(--ink)',
            letterSpacing: '-0.03em',
            lineHeight: 1.2,
            margin: '0 0 10px 0',
          }}
        >
          Navie optimizes every order{' '}
          <span style={{ color: 'var(--plum)' }}>without missing the window.</span>
        </h2>
        <p
          style={{
            fontSize: '1.05rem',
            color: 'var(--ink-2)',
            margin: 0,
            lineHeight: 1.5,
            maxWidth: '680px',
          }}
        >
          The agent compares payout, real-time traffic, risk, return to anchor, and opportunity cost to decide in milliseconds what's worth accepting.
        </p>
      </div>

      {/* Grid de 2 Columnas (Pixel Canvas con fondo claro + Botón interactivo al lado) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '24px',
          alignItems: 'stretch',
        }}
      >
        {/* Columna 1: fondo animado + Navie, igual que en el playground */}
        <NavieBackgroundPanel mode="happy" minHeight={360} />

        {/* Columna 2: Tarjeta al lado con el Botón y estilo Grid */}
        <div
          style={{
            borderRadius: '16px',
            backgroundColor: 'var(--card)',
            backgroundImage:
              'linear-gradient(to right, var(--surface-low) 1px, transparent 1px), linear-gradient(to bottom, var(--surface-low) 1px, transparent 1px)',
            backgroundSize: '24px 24px',
            border: '1px solid var(--hairline)',
            boxShadow: 'none',
            padding: 'clamp(28px, 4vw, 36px)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            textAlign: 'left',
            gap: '20px',
            boxSizing: 'border-box',
            position: 'relative',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <h3
              style={{
                fontSize: 'clamp(1.3rem, 2.2vw, 1.7rem)',
                fontWeight: 800,
                color: 'var(--ink)',
                lineHeight: 1.25,
                margin: 0,
                letterSpacing: '-0.02em',
              }}
            >
              The shift is played minute by minute.
            </h3>

            <p
              style={{
                fontSize: '0.95rem',
                color: 'var(--ink-2)',
                lineHeight: 1.55,
                margin: 0,
              }}
            >
              Navie doesn't accept everything that comes in: it evaluates if the order pays more than the value of that time, if you can return to your anchor, and if the route fits the shift constraints.
            </p>

            {/* Puntos técnicos de grid */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.88rem',
                  color: 'var(--ink-2)',
                  fontWeight: 600,
                }}
              >
                <span style={{ color: 'var(--emerald)', fontWeight: 800 }}>✓</span>
                Opportunity cost per remaining minute
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.88rem',
                  color: 'var(--ink-2)',
                  fontWeight: 600,
                }}
              >
                <span style={{ color: 'var(--emerald)', fontWeight: 800 }}>✓</span>
                Feasible return to anchor and safety constraints
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.88rem',
                  color: 'var(--ink-2)',
                  fontWeight: 600,
                }}
              >
                <span style={{ color: 'var(--emerald)', fontWeight: 800 }}>✓</span>
                Batching and routing to extract more value from the same shift
              </div>
            </div>
          </div>

          {/* El botón de acción */}
          <div
            style={{
              display: 'flex',
              gap: '12px',
              flexWrap: 'wrap',
              width: '100%',
              marginTop: '8px',
            }}
          >
            <Link
              to="/sim"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '10px',
                padding: '12px 26px',
                backgroundColor: 'var(--ink)',
                color: '#ffffff',
                fontSize: '0.95rem',
                fontWeight: 700,
                borderRadius: '8px',
                textDecoration: 'none',
                boxShadow: 'none',
                transition: 'all 0.15s ease',
                border: '1px solid var(--ink)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--plum)'
                e.currentTarget.style.borderColor = 'var(--plum)'
                e.currentTarget.style.transform = 'translateY(-1px)'
                e.currentTarget.style.boxShadow = 'none'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--ink)'
                e.currentTarget.style.borderColor = 'var(--ink)'
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              See Navie in action
            </Link>

            <Link
              to="/sim"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '12px 20px',
                backgroundColor: 'var(--surface-low)',
                color: 'var(--ink)',
                fontSize: '0.95rem',
                fontWeight: 600,
                borderRadius: '8px',
                textDecoration: 'none',
                border: '1px solid var(--hairline)',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--surface)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--surface-low)'
              }}
            >
              Go to the simulation ›
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}
