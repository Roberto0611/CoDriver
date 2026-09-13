// Landing: el marco de la pagina (fondo con grid y columna central). Cada seccion
// vive en src/landing/ para que ningun archivo pase de 500 lineas.

import { LandingFindings } from './landing/LandingFindings'
import { LandingHero } from './landing/LandingHero'
import { LandingNavbar } from './landing/LandingNavbar'

export default function LandingPage() {
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
          width: 'calc(100% - clamp(24px, 6vw, 96px))',
          maxWidth: '1240px',
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
        }}
      >
        {/* ── Navbar (Estilo Browserbase) ── */}
        <LandingNavbar />

        {/* ── Hero Section (con USA Map Canvas de fondo y Grid Style) ── */}
        <LandingHero />

        {/* ── Sección de Contenido Grid y Columna de 2 ── */}
        <LandingFindings />
      </div>
    </div>
  )
}
