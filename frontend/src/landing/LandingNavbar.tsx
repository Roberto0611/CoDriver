// Barra superior del landing: logo de Navie, enlaces y botones de cuenta.

import { Link } from 'react-router-dom'
import { NavieCompass } from '../navie/NavieCompass'

export function LandingNavbar() {
  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 24px',
        backgroundColor: 'var(--card)',
        borderBottom: '1px solid var(--hairline)',
        width: '100%',
        boxSizing: 'border-box',
        zIndex: 50,
        overflowX: 'auto',
      }}
    >
      {/* Logo y Nombre */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div
          style={{
            width: '40px',
            height: '40px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <div
            style={{
              transform: 'scale(0.2)',
              transformOrigin: 'center center',
              position: 'absolute',
            }}
          >
            <NavieCompass mode="idle" />
          </div>
        </div>
        <span
          style={{
            fontSize: '1.25rem',
            fontWeight: 800,
            color: 'var(--ink)',
            letterSpacing: '-0.02em',
          }}
        >
          CoDrive
        </span>
      </div>


      {/* Botones Derecha */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          fontWeight: 600,
          fontSize: '0.9rem',
        }}
      >
        <a 
          href="https://github.com/Roberto0611/hackmty-infosys" 
          target="_blank" 
          rel="noreferrer" 
          style={{ textDecoration: 'none', color: 'var(--ink)', display: 'flex', alignItems: 'center', gap: '4px' }}
          onMouseEnter={(e) => {
            const star = e.currentTarget.querySelector('.github-star') as HTMLElement
            if (star) star.style.color = '#FACC15'
          }}
          onMouseLeave={(e) => {
            const star = e.currentTarget.querySelector('.github-star') as HTMLElement
            if (star) star.style.color = 'inherit'
          }}
        >
          Go to Github
          <span className="github-star" style={{ fontSize: '1.1em', transition: 'color 0.2s ease' }}>★</span>
        </a>
        <Link
          to="/sim"
          style={{
            backgroundColor: 'var(--ink)',
            color: 'var(--canvas)',
            padding: '8px 18px',
            borderRadius: '9999px',
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          Go to the simulation
          <span style={{ fontSize: '1.1em' }}>›</span>
        </Link>
      </div>
    </header>
  )
}
