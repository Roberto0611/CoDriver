// Hero del landing: video pixelado de fondo, titulo, subtitulo y el boton al demo.

import { Link } from 'react-router-dom'
import PixelCanvasBackground from '../PixelCanvasBackground'

export function LandingHero() {
  return (
    <section
      style={{
        position: 'relative',
        width: '100%',
        height: 'clamp(600px, 80vh, 800px)',
        minHeight: '600px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'flex-start',
        paddingTop: 'clamp(70px, 15vh, 120px)',
        paddingLeft: '20px',
        paddingRight: '20px',
        textAlign: 'center',
        overflow: 'hidden',
        boxSizing: 'border-box',
        backgroundColor: 'var(--ink)',
        backgroundImage:
          'linear-gradient(to right, rgba(255, 255, 255, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.05) 1px, transparent 1px)',
        backgroundSize: '24px 24px',
        borderBottom: '1px solid var(--hairline)',
      }}
    >
      {/* Fondo interactivo de Video (.mp4) con PixelCanvas */}
      <PixelCanvasBackground
        src="/tec-fondo-compact-ezgif.com-gif-to-mp4-converter.mp4"
        pixelSize={8}
        overlayOpacity={0}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          zIndex: 0,
        }}
      />

      {/* Contenido del Hero sobre el mapa */}
      <div
        style={{
          position: 'relative',
          zIndex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          maxWidth: '900px',
          width: '100%',
        }}
      >
        {/* ── Main Highlighted Title ── */}
        <h1
          style={{
            margin: 0,
            padding: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span
            style={{
              backgroundColor: 'var(--plum)',
              color: '#ffffff',
              padding: '4px 16px',
              fontSize: 'clamp(2rem, 4.6vw, 3.4rem)',
              fontWeight: 800,
              letterSpacing: '-0.03em',
              lineHeight: 1.18,
              display: 'inline-block',
              borderRadius: '3px',
              boxShadow: 'none',
            }}
          >
            Navie decide qué aceptar y qué rechazar entre clases.
          </span>
        </h1>

        {/* ── Subtitle ── */}
        <p
          style={{
            color: 'var(--ink)',
            fontSize: 'clamp(0.85rem, 1.5vw, 1.2rem)',
            fontWeight: 600,
            maxWidth: '560px',
            marginTop: '26px',
            marginBottom: '26px',
            lineHeight: 1.4,
            letterSpacing: '-0.01em',
            backgroundColor: 'var(--card)',
          }}
        >
          Un copiloto de entrega para estudiantes: calcula el costo de oportunidad, revisa si puedes
          volver a clase y explica cada decisión en voz alta.
        </p>

        {/* ── CTA Buttons ── */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <Link
            to="/map"
            style={{
              backgroundColor: 'var(--card)',
              color: 'var(--ink)',
              borderRadius: '9999px',
              padding: '10px 22px',
              fontSize: '0.95rem',
              fontWeight: 700,
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'transform 0.15s ease, opacity 0.15s ease',
              boxShadow: 'none',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-1px)'
              e.currentTarget.style.opacity = '0.92'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.opacity = '1'
            }}
          >
            Explora el demo ›
          </Link>
        </div>
      </div>
    </section>
  )
}
