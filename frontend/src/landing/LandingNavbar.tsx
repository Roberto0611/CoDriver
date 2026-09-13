// Barra superior del landing: logo de Navie, enlaces y botones de cuenta.

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
          Codrive
        </span>
      </div>

      {/* Enlaces de Navegación (Centro) */}
      <nav
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '24px',
          fontWeight: 600,
          fontSize: '0.9rem',
          color: 'var(--ink)',
        }}
      >
        <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>
          Platform
        </a>
        <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>
          Solutions
        </a>
        <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>
          Resources
        </a>
        <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>
          Pricing
        </a>
        <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>
          Docs
        </a>
      </nav>

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
        <a href="#" style={{ textDecoration: 'none', color: 'var(--ink)' }}>
          Log in
        </a>
        <a href="#" style={{ textDecoration: 'none', color: 'var(--ink)' }}>
          Sign up
        </a>
        <a
          href="#"
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
          Get a demo
          <span style={{ fontSize: '1.1em' }}>›</span>
        </a>
      </div>
    </header>
  )
}
