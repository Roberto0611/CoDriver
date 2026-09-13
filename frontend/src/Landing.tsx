import { Link } from 'react-router-dom'
import PixelCanvasBackground from './PixelCanvasBackground'
import NavieBackgroundPanel from './NavieBackgroundPanel'
import tecFondoGif from './tec-fondo-compact.gif'

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
            backgroundColor: 'var(--ink)',
            backgroundImage:
              'linear-gradient(to right, rgba(255, 255, 255, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.05) 1px, transparent 1px)',
            backgroundSize: '24px 24px',
            borderBottom: '1px solid var(--hairline)',
          }}
        >
          {/* Fondo interactivo de Video (.mp4) con PixelCanvas */}
          <PixelCanvasBackground
            src={tecFondoGif}
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
                fontSize: 'clamp(1rem, 2vw, 1.25rem)',
                fontWeight: 600,
                maxWidth: '560px',
                marginTop: '26px',
                marginBottom: '26px',
                lineHeight: 1.4,
                letterSpacing: '-0.01em',
                backgroundColor: 'var(--card)',
              }}
            >
              Un copiloto de entrega para estudiantes: calcula el costo de oportunidad, revisa si
              puedes volver a clase y explica cada decisión en voz alta.
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
                color: 'var(--ink)',
                letterSpacing: '-0.03em',
                lineHeight: 1.2,
                margin: '0 0 10px 0',
              }}
            >
              Navie optimiza cada pedido{' '}
              <span style={{ color: 'var(--plum)' }}>sin perder la ventana.</span>.
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
              El agente compara pago, tiempo real, riesgo, regreso al ancla y costo de oportunidad
              para decidir en milisegundos qué vale la pena aceptar.
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
                  El turno se juega minuto a minuto.
                </h3>

                <p
                  style={{
                    fontSize: '0.95rem',
                    color: 'var(--ink-2)',
                    lineHeight: 1.55,
                    margin: 0,
                  }}
                >
                  Navie no acepta todo lo que llega: evalúa si el pedido paga más que el valor de
                  ese tiempo, si puedes regresar a tu ancla y si la ruta encaja con las
                  restricciones del turno.
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
                      color: 'var(--ink-2)',
                      fontWeight: 600,
                    }}
                  >
                    <span style={{ color: 'var(--emerald)', fontWeight: 800 }}>✓</span>
                    Costo de oportunidad por minuto restante
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
                    Regreso factible al ancla y restricciones de seguridad
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
                    Batching y ruteo para sacar más valor del mismo turno
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
                  Ver a Navie en acción
                </Link>

                <Link
                  to="/map"
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
                  Explorar el mapa ›
                </Link>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
