import PixelCanvasBackground from './PixelCanvasBackground'
import { NavieCompass, type CompassMode } from './navie/NavieCompass'
import bgImage from './fondo-navie-landing.png'

export interface NavieBackgroundPanelProps {
  mode?: CompassMode
  minHeight?: number
}

export default function NavieBackgroundPanel({
  mode = 'happy',
  minHeight = 360,
}: NavieBackgroundPanelProps) {
  return (
    <>
      <style>{`
        @keyframes navieFloatImage {
          0% { transform: translate3d(0, 0, 0) scale(1); }
          50% { transform: translate3d(0, -5px, 0) scale(1.02); }
          100% { transform: translate3d(0, 4px, 0) scale(1.01); }
        }
      `}</style>
      <div
        style={{
          position: 'relative',
          width: '100%',
          minHeight,
          height: '100%',
          borderRadius: 16,
          overflow: 'hidden',
          backgroundColor: 'var(--surface-low)',
          backgroundImage:
            'linear-gradient(to right, rgba(104, 73, 89, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(104, 73, 89, 0.05) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          border: '1px solid var(--hairline)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          zIndex: 0,
          pointerEvents: 'none',
          animation: 'navieFloatImage 9s ease-in-out infinite alternate',
          willChange: 'transform',
        }}
      >
        <PixelCanvasBackground
          src={bgImage}
          pixelSize={5}
          shapeMode="circles"
          colorMode="greyscale"
          contrast={100}
          lightness={100}
          interactive={false}
          overlayOpacity={0.12}
          overlayBlur={0}
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 0,
            pointerEvents: 'none',
            animation: 'navieFloatImage 9s ease-in-out infinite alternate',
            willChange: 'transform',
          }}
        />

        <div
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 1,
            background:
              'radial-gradient(circle at center, rgba(255,255,255,0.16), rgba(255,255,255,0.02) 45%, rgba(255,255,255,0) 72%)',
          }}
        />

        <div
          style={{
            position: 'relative',
            zIndex: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            height: '100%',
            padding: 24,
            transform: 'scale(1.08)',
          }}
        >
          <NavieCompass mode={mode} />
        </div>
      </div>
      </div>
    </>
  )
}
