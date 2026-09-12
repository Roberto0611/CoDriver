import { Link } from 'react-router-dom'
import PixelCanvasBackground from './PixelCanvasBackground'
import bloudUrl from './bloud.svg'

export default function LandingPage() {
  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100%',
        backgroundColor: '#f8fafc',
        backgroundImage:
          'linear-gradient(to right, rgba(0, 0, 0, 0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(0, 0, 0, 0.03) 1px, transparent 1px)',
        backgroundSize: '24px 24px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        fontFamily: 'var(--font-sans)',
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
          backgroundColor: '#ffffff',
          borderLeft: '1px solid #e2e8f0',
          borderRight: '1px solid #e2e8f0',
          boxShadow: '0 0 45px rgba(0, 0, 0, 0.035)',
          display: 'flex',
          flexDirection: 'column',
          boxSizing: 'border-box',
          minHeight: '100vh',
        }}
      >
        {/* ── Hero Section (con USA Map Canvas de fondo y Grid Style) ── */}
        <section
          style={{
            position: 'relative',
            width: '100%',
            height: 'clamp(460px, 60vh, 580px)',
            minHeight: '460px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'flex-start',
            paddingTop: 'clamp(36px, 6vh, 60px)',
            paddingLeft: '20px',
            paddingRight: '20px',
            textAlign: 'center',
            overflow: 'hidden',
            boxSizing: 'border-box',
            backgroundColor: '#090d16',
            backgroundImage:
              'linear-gradient(to right, rgba(255, 255, 255, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.05) 1px, transparent 1px)',
            backgroundSize: '24px 24px',
            borderBottom: '1px solid rgba(226, 232, 240, 0.8)',
          }}
        >
          {/* Fondo interactivo de Video (.mp4) con PixelCanvas */}
          <PixelCanvasBackground
            pixelSize={4}
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
                  backgroundColor: '#ff3c00',
                  color: '#ffffff',
                  padding: '4px 16px',
                  fontSize: 'clamp(2rem, 4.6vw, 3.4rem)',
                  fontWeight: 800,
                  letterSpacing: '-0.03em',
                  lineHeight: 1.18,
                  display: 'inline-block',
                  borderRadius: '3px',
                  boxShadow: '0 6px 20px rgba(255, 60, 0, 0.3)',
                }}
              >
                Vulnerabilidad social y de salud, código postal por código postal.
              </span>
            </h1>

            {/* ── Subtitle ── */}
            <p
              style={{
                color: 'black',
                fontSize: 'clamp(1rem, 2vw, 1.25rem)',
                fontWeight: 600,
                maxWidth: '560px',
                marginTop: '26px',
                marginBottom: '26px',
                lineHeight: 1.4,
                letterSpacing: '-0.01em',
                backgroundColor: 'white',
              }}
            >
              hola{' '}
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
                  backgroundColor: '#ffffff',
                  color: '#000000',
                  borderRadius: '9999px',
                  padding: '10px 22px',
                  fontSize: '0.95rem',
                  fontWeight: 700,
                  textDecoration: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'transform 0.15s ease, opacity 0.15s ease',
                  boxShadow: '0 4px 14px rgba(255, 255, 255, 0.2)',
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
                Abre nuestro mapa ›
              </Link>
            </div>
          </div>
        </section>

        {/* ── Sección de Contenido Grid y Columna de 2 ── */}
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
                color: '#0f172a',
                letterSpacing: '-0.03em',
                lineHeight: 1.2,
                margin: '0 0 10px 0',
              }}
            >
              Pregúntale a <span style={{ color: '#ff3c00' }}>Cloudy</span> lo que quieras saber.
            </h2>
            <p
              style={{
                fontSize: '1.05rem',
                color: '#475569',
                margin: 0,
                lineHeight: 1.5,
                maxWidth: '680px',
              }}
            >
              Escribe tu pregunta en español y Cloudy la traduce a una consulta sobre la base real
              de códigos postales, sin inventar cifras.
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
            {/* Columna 1: Pixel Canvas Background actual (SIN FONDO NEGRO, Estilo Grid Blueprint Claro) */}
            <div
              style={{
                position: 'relative',
                borderRadius: '16px',
                overflow: 'hidden',
                minHeight: '360px',
                backgroundColor: '#ffffff',
                backgroundImage:
                  'linear-gradient(to right, #f1f5f9 1px, transparent 1px), linear-gradient(to bottom, #f1f5f9 1px, transparent 1px)',
                backgroundSize: '24px 24px',
                border: '1px solid #e2e8f0',
                boxShadow:
                  '0 10px 25px -5px rgba(0, 0, 0, 0.04), 0 8px 10px -6px rgba(0, 0, 0, 0.04)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                padding: '20px',
                boxSizing: 'border-box',
              }}
            >
              {/* Fondo de Canvas Animado con bloud.svg - OJO: SIN overlay ni fondo negro */}
              <PixelCanvasBackground
                src={bloudUrl}
                pixelSize={6}
                colorMode="full"
                overlayOpacity={0}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '100%',
                  zIndex: 1,
                }}
              />
            </div>

            {/* Columna 2: Tarjeta al lado con el Botón y estilo Grid */}
            <div
              style={{
                borderRadius: '16px',
                backgroundColor: '#ffffff',
                backgroundImage:
                  'linear-gradient(to right, #f8fafc 1px, transparent 1px), linear-gradient(to bottom, #f8fafc 1px, transparent 1px)',
                backgroundSize: '24px 24px',
                border: '1px solid #e2e8f0',
                boxShadow:
                  '0 10px 25px -5px rgba(0, 0, 0, 0.04), 0 8px 10px -6px rgba(0, 0, 0, 0.04)',
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
                    color: '#0f172a',
                    lineHeight: 1.25,
                    margin: 0,
                    letterSpacing: '-0.02em',
                  }}
                >
                  Del hallazgo a la decisión, en un mismo lugar
                </h3>

                <p
                  style={{
                    fontSize: '0.95rem',
                    color: '#64748b',
                    lineHeight: 1.55,
                    margin: 0,
                  }}
                >
                  Filtra por estado, compara códigos postales vecinos con salud opuesta y asigna
                  recursos limitados a las zonas donde más rinden, todo con el margen de error real
                  de cada estimación.
                </p>

                {/* Puntos técnicos de grid */}
                <div
                  style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '0.88rem',
                      color: '#334155',
                      fontWeight: 600,
                    }}
                  >
                    <span style={{ color: '#10b981', fontWeight: 800 }}>✓</span>
                    Vulnerabilidad y confiabilidad del dato por ZCTA
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '0.88rem',
                      color: '#334155',
                      fontWeight: 600,
                    }}
                  >
                    <span style={{ color: '#10b981', fontWeight: 800 }}>✓</span>
                    Comparador de vecinos con salud opuesta
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '0.88rem',
                      color: '#334155',
                      fontWeight: 600,
                    }}
                  >
                    <span style={{ color: '#10b981', fontWeight: 800 }}>✓</span>
                    Asignador de recursos por alcance y gravedad
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
                  to="/map"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '10px',
                    padding: '12px 26px',
                    backgroundColor: '#0f172a',
                    color: '#ffffff',
                    fontSize: '0.95rem',
                    fontWeight: 700,
                    borderRadius: '8px',
                    textDecoration: 'none',
                    boxShadow: '0 4px 14px rgba(15, 23, 42, 0.15)',
                    transition: 'all 0.15s ease',
                    border: '1px solid #0f172a',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#ff3c00'
                    e.currentTarget.style.borderColor = '#ff3c00'
                    e.currentTarget.style.transform = 'translateY(-1px)'
                    e.currentTarget.style.boxShadow = '0 6px 20px rgba(255, 60, 0, 0.3)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = '#0f172a'
                    e.currentTarget.style.borderColor = '#0f172a'
                    e.currentTarget.style.transform = 'translateY(0)'
                    e.currentTarget.style.boxShadow = '0 4px 14px rgba(15, 23, 42, 0.15)'
                  }}
                >
                  Habla con Cloudy en el mapa
                </Link>

                <Link
                  to="/map"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '12px 20px',
                    backgroundColor: '#f8fafc',
                    color: '#0f172a',
                    fontSize: '0.95rem',
                    fontWeight: 600,
                    borderRadius: '8px',
                    textDecoration: 'none',
                    border: '1px solid #cbd5e1',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#f1f5f9'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = '#f8fafc'
                  }}
                >
                  Abrir mapa interactivo ›
                </Link>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
