// Hero del landing: video pixelado de fondo, titulo, subtitulo y el boton al demo.

import { Link } from 'react-router-dom'
import { Maximize2, Minimize2 } from 'lucide-react'
import PixelCanvasBackground from '../PixelCanvasBackground'

export function LandingHero({
  isExpanded = false,
  toggleExpand = () => {},
}: {
  isExpanded?: boolean
  toggleExpand?: () => void
}) {
  return (
    <section
      style={{
        position: 'relative',
        width: '100%',
        height: isExpanded ? '100vh' : 'clamp(600px, 80vh, 800px)',
        minHeight: '600px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: isExpanded ? 'center' : 'flex-start',
        paddingTop: isExpanded ? '0' : 'clamp(70px, 15vh, 120px)',
        transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
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
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '100vw',
          height: '100vh',
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
          opacity: isExpanded ? 0 : 1,
          pointerEvents: isExpanded ? 'none' : 'auto',
          transition: 'opacity 0.4s ease',
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
            Navie decides what to accept and what to reject between classes.
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
          A delivery copilot for students: calculates opportunity cost, checks if you can make it
          back to class, and explains every decision out loud.
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
            to="/sim"
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
            Go to the simulation ›
          </Link>
        </div>
      </div>

      {/* ── Bottom Left Location Text ── */}
      <div
        style={{
          position: 'absolute',
          bottom: '35px',
          left: '24px',
          zIndex: 2,
          color: '#ffffff',
          fontSize: 'clamp(1.5rem, 3vw, 2.5rem)',
          fontWeight: 800,
          letterSpacing: '-0.02em',
          opacity: isExpanded ? 1 : 0,
          transition: 'opacity 0.4s ease',
          pointerEvents: isExpanded ? 'auto' : 'none',
          textShadow: '0 2px 12px rgba(0,0,0,0.4)',
        }}
      >
        Monterrey, Nuevo Leon, Mexico
      </div>

      {/* ── Bottom Right Expand Button ── */}
      <button
        onClick={toggleExpand}
        style={{
          position: 'absolute',
          bottom: '24px',
          right: '24px',
          zIndex: 2,
          background: 'rgba(0, 0, 0, 0.5)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          borderRadius: '8px',
          padding: '8px',
          color: 'white',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease',
          backdropFilter: 'blur(4px)',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'rgba(0, 0, 0, 0.8)'
          e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.4)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'rgba(0, 0, 0, 0.5)'
          e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)'
        }}
      >
        {isExpanded ? <Minimize2 size={20} /> : <Maximize2 size={20} />}
      </button>
    </section>
  )
}
