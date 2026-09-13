import { useState, useEffect } from 'react'
import { LandingFindings } from './landing/LandingFindings'
import { LandingHero } from './landing/LandingHero'
import { LandingNavbar } from './landing/LandingNavbar'

export default function LandingPage() {
  const [isExpanded, setIsExpanded] = useState(false)

  useEffect(() => {
    if (isExpanded) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = 'auto'
    }
    return () => {
      document.body.style.overflow = 'auto'
    }
  }, [isExpanded])

  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100%',
        backgroundColor: 'var(--canvas)',
        backgroundImage:
          'linear-gradient(to right, rgba(24, 21, 26, 0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(24, 21, 26, 0.04) 1px, transparent 1px)',
        backgroundSize: '24px 24px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        fontFamily: 'var(--font)',
        boxSizing: 'border-box',
        overflowX: 'hidden',
      }}
    >
      {/* Contenedor central con Margin-Left y Margin-Right precisos y bordes de grid */}
      <div
        style={{
          width: isExpanded ? '100%' : 'calc(100% - clamp(24px, 6vw, 96px))',
          maxWidth: isExpanded ? '100%' : '1240px',
          marginLeft: 'auto',
          marginRight: 'auto',
          backgroundColor: 'var(--card)',
          borderLeft: '1px solid var(--hairline)',
          borderRight: '1px solid var(--hairline)',
          boxShadow: 'none',
          display: 'flex',
          flexDirection: 'column',
          boxSizing: 'border-box',
          minHeight: '100vh',
          transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
        }}
      >
        {/* ── Navbar (Estilo Browserbase) ── */}
        <div
          style={{
            overflow: 'hidden',
            maxHeight: isExpanded ? '0' : '200px',
            opacity: isExpanded ? 0 : 1,
            transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        >
          <LandingNavbar />
        </div>

        {/* ── Hero Section (con USA Map Canvas de fondo y Grid Style) ── */}
        <LandingHero isExpanded={isExpanded} toggleExpand={() => setIsExpanded(!isExpanded)} />

        {/* ── Sección de Contenido Grid y Columna de 2 ── */}
        <div
          style={{
            overflow: 'hidden',
            maxHeight: isExpanded ? '0' : '2000px',
            opacity: isExpanded ? 0 : 1,
            transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        >
          <LandingFindings />
        </div>
      </div>
    </div>
  )
}
