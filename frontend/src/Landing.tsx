import { Link } from 'react-router-dom'
import PixelCanvasBackground from './PixelCanvasBackground'
import NavieBackgroundPanel from './NavieBackgroundPanel'
import { NavieCompass } from './navie/NavieCompass'

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
            <div style={{ width: '40px', height: '40px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', position: 'relative' }}>
              <div style={{ transform: 'scale(0.2)', transformOrigin: 'center center', position: 'absolute' }}>
                <NavieCompass mode="idle" />
              </div>
            </div>
            <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ink)', letterSpacing: '-0.02em' }}>
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
            <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>Platform</a>
            <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>Solutions</a>
            <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>Resources</a>
            <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>Pricing</a>
            <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>Docs</a>
          </nav>

          {/* Botones Derecha */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontWeight: 600, fontSize: '0.9rem' }}>
            <a href="#" style={{ textDecoration: 'none', color: 'var(--ink)' }}>Log in</a>
            <a href="#" style={{ textDecoration: 'none', color: 'var(--ink)' }}>Sign up</a>
            <a href="#" style={{
              backgroundColor: 'var(--ink)',
              color: 'var(--canvas)',
              padding: '8px 18px',
              borderRadius: '9999px',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              Get a demo 
              <span style={{ fontSize: '1.1em' }}>›</span>
            </a>
          </div>
        </header>

        {/* â”€â”€ Hero Section (con USA Map Canvas de fondo y Grid Style) â”€â”€ */}
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
          src='/tec-fondo-compact-ezgif.com-gif-to-mp4-converter.mp4'
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
          {/* â”€â”€ Main Highlighted Title â”€â”€ */}
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

          {/* â”€â”€ Subtitle â”€â”€ */}
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
            A delivery copilot for students: calculates opportunity cost, checks if you can make it back to class, and explains every decision out loud.
          </p>

          {/* â”€â”€ CTA Buttons â”€â”€ */}
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
                e.currentTarget.style.transform = 'translateY(-1px)';
                e.currentTarget.style.opacity = '0.92';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.opacity = '1';
              }}
            >
              Explore the demo ›
            </Link>
          </div>
        </div>
      </section>

      {/* â”€â”€ SecciÃ³n de Contenido Grid y Columna de 2 â”€â”€ */}
      <section
        style={{
          width: '100%',
          maxWidth: '1200px',
          margin: '0 auto',
          padding: '54px 20px 80px 20px',
          boxSizing: 'border-box',
        }}
      >
        {/* Encabezado de la secciÃ³n de hallazgos */}
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
            Navie optimizes every order <span style={{ color: 'var(--plum)' }}>without missing the window.</span>
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

        {/* Grid de 2 Columnas (Pixel Canvas con fondo claro + BotÃ³n interactivo al lado) */}
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

          {/* Columna 2: Tarjeta al lado con el BotÃ³n y estilo Grid */}
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

              {/* Puntos tÃ©cnicos de grid */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.88rem', color: 'var(--ink-2)', fontWeight: 600 }}>
                  <span style={{ color: 'var(--emerald)', fontWeight: 800 }}>✓</span>
                  Opportunity cost per remaining minute
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.88rem', color: 'var(--ink-2)', fontWeight: 600 }}>
                  <span style={{ color: 'var(--emerald)', fontWeight: 800 }}>✓</span>
                  Feasible return to anchor and safety constraints
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.88rem', color: 'var(--ink-2)', fontWeight: 600 }}>
                  <span style={{ color: 'var(--emerald)', fontWeight: 800 }}>✓</span>
                  Batching and routing to extract more value from the same shift
                </div>
              </div>
            </div>

            {/* El botÃ³n de acciÃ³n */}
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', width: '100%', marginTop: '8px' }}>
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
                  e.currentTarget.style.backgroundColor = 'var(--plum)';
                  e.currentTarget.style.borderColor = 'var(--plum)';
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--ink)';
                  e.currentTarget.style.borderColor = 'var(--ink)';
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                See Navie in action
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
                  e.currentTarget.style.backgroundColor = 'var(--surface)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--surface-low)';
                }}
              >
                 Explore the map ›
              </Link>
            </div>
          </div>
        </div>
      </section>
      </div>
    </div>
  );
}

