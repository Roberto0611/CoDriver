import React, { useEffect, useRef } from 'react'

export interface PixelCanvasBackgroundProps {
  /** Ruta del archivo de video o imagen (por defecto usa la configurada en FrontHelp) */
  src?: string
  pixelSize?: number
  shapeMode?: 'circles' | 'squares' | 'octagons' | 'small-circles-squares'
  colorMode?: 'palette' | 'full' | 'greyscale'
  palette?: string[]
  contrast?: number
  lightness?: number
  interactive?: boolean
  overlayOpacity?: number
  overlayBlur?: number
  className?: string
  style?: React.CSSProperties
}

// ── Configuraciones por defecto exportadas desde FrontHelp ──────────────────
const DEFAULT_VIDEO_SRC = '/tec-fondo-compact-ezgif.com-gif-to-mp4-converter.mp4'
const DEFAULT_PIXEL_SIZE = 3
const DEFAULT_SHAPE_MODE = 'circles'
const DEFAULT_COLOR_MODE = 'full'
const DEFAULT_PALETTE = ['#FF4500', '#0000CD', '#00C800', '#FFD700']
const DEFAULT_CONTRAST = 60
const DEFAULT_LIGHTNESS = 100

const hexToRgb = (hex: string) => {
  const clean = hex.replace('#', '')
  const bigint = parseInt(clean, 16)
  if (clean.length === 3) {
    const r = (bigint >> 8) & 15
    const g = (bigint >> 4) & 15
    const b = bigint & 15
    return { r: (r << 4) | r, g: (g << 4) | g, b: (b << 4) | b }
  }
  return {
    r: (bigint >> 16) & 255,
    g: (bigint >> 8) & 255,
    b: bigint & 255,
  }
}

const colorDistSq = (r1: number, g1: number, b1: number, r2: number, g2: number, b2: number) =>
  (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2

const drawOctagon = (ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number) => {
  ctx.beginPath()
  for (let i = 0; i < 8; i++) {
    const angle = (i * Math.PI) / 4 + Math.PI / 8
    const vx = cx + r * Math.cos(angle)
    const vy = cy + r * Math.sin(angle)
    if (i === 0) ctx.moveTo(vx, vy)
    else ctx.lineTo(vx, vy)
  }
  ctx.closePath()
  ctx.fill()
}

export const PixelCanvasBackground: React.FC<PixelCanvasBackgroundProps> = ({
  src = DEFAULT_VIDEO_SRC,
  pixelSize = DEFAULT_PIXEL_SIZE,
  shapeMode = DEFAULT_SHAPE_MODE,
  colorMode = DEFAULT_COLOR_MODE,
  palette = DEFAULT_PALETTE,
  contrast = DEFAULT_CONTRAST,
  lightness = DEFAULT_LIGHTNESS,
  interactive = true,
  overlayOpacity = 0.45,
  overlayBlur = 1,
  className = '',
  style = {},
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const mediaRef = useRef<HTMLVideoElement | HTMLImageElement | null>(null)
  const offscreenRef = useRef<HTMLCanvasElement | null>(null)
  const animFrameIdRef = useRef<number | null>(null)
  const mousePosRef = useRef<{ x: number; y: number }>({ x: -1000, y: -1000 })

  useEffect(() => {
    const isVideo = /\.(mp4|webm|ogg|mov)(\?.*)?$/i.test(src)
    let videoEl: HTMLVideoElement | null = null
    let imageEl: HTMLImageElement | null = null
    let isReady = false

    if (isVideo) {
      videoEl = document.createElement('video')
      videoEl.src = src
      videoEl.crossOrigin = 'anonymous'
      videoEl.loop = true
      videoEl.muted = true
      videoEl.defaultMuted = true
      videoEl.playsInline = true
      videoEl.autoplay = true

      // FIX: Engañar al navegador para que no congele el video por ser "invisible"
      videoEl.style.position = 'absolute'
      videoEl.style.width = '1px'
      videoEl.style.height = '1px'
      videoEl.style.opacity = '0.01'
      videoEl.style.pointerEvents = 'none'
      document.body.appendChild(videoEl)

      videoEl.onloadeddata = () => {
        isReady = true
      }
      videoEl.play().catch(() => {})
      mediaRef.current = videoEl
    } else {
      imageEl = new Image()
      imageEl.crossOrigin = 'anonymous'
      imageEl.src = src
      imageEl.onload = () => {
        isReady = true
      }
      mediaRef.current = imageEl
    }

    const offscreen = document.createElement('canvas')
    offscreenRef.current = offscreen
    const offCtx = offscreen.getContext('2d', { willReadFrequently: true })

    const canvas = canvasRef.current
    if (!canvas || !offCtx) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const paletteRgb = palette.map(hexToRgb)

    const updateDimensions = () => {
      if (!canvas) return
      // El canvas ya debería estar estirado al 100% de su contenedor por CSS
      // o usamos el parentElement para saber el tamaño real que debe ocupar
      const parent = canvas.parentElement
      const w = parent ? parent.clientWidth : window.innerWidth
      const h = parent ? parent.clientHeight : window.innerHeight
      const dpr = Math.min(window.devicePixelRatio || 1, 2)

      canvas.width = Math.floor(w * dpr)
      canvas.height = Math.floor(h * dpr)
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`

      offscreen.width = w
      offscreen.height = h
    }
    updateDimensions()
    
    let resizeObserver: ResizeObserver | null = null
    let resizeTimeout: ReturnType<typeof setTimeout> | null = null
    if (canvas.parentElement) {
      resizeObserver = new ResizeObserver(() => {
        if (resizeTimeout) clearTimeout(resizeTimeout)
        resizeTimeout = setTimeout(() => {
          updateDimensions()
        }, 300) // Espera a que termine la transicion CSS para repintar
      })
      resizeObserver.observe(canvas.parentElement)
    } else {
      window.addEventListener('resize', updateDimensions)
    }

    const handleMouseMove = (e: MouseEvent) => {
      if (!canvasRef.current) return
      const rect = canvasRef.current.getBoundingClientRect()
      mousePosRef.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      }
    }
    const handleMouseLeave = () => {
      mousePosRef.current = { x: -1000, y: -1000 }
    }

    if (interactive) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseleave', handleMouseLeave)
    }

    const render = () => {
      const media = mediaRef.current
      const w = offscreen.width
      const h = offscreen.height
      const dpr = Math.min(window.devicePixelRatio || 1, 2)

      const canDraw =
        isReady &&
        media &&
        ((isVideo && videoEl && videoEl.readyState >= 2) ||
          (!isVideo && imageEl && imageEl.complete))

      if (canDraw && media) {
        const mw =
          (media as HTMLVideoElement).videoWidth || (media as HTMLImageElement).naturalWidth || w
        const mh =
          (media as HTMLVideoElement).videoHeight || (media as HTMLImageElement).naturalHeight || h

        offCtx.clearRect(0, 0, w, h)
        offCtx.filter = `contrast(${contrast}%) brightness(${lightness}%)`

        const mRatio = mw / mh
        const cRatio = w / h
        let dw = w,
          dh = h,
          dx = 0,
          dy = 0
        if (cRatio > mRatio) {
          dh = w / mRatio
          dy = (h - dh) / 2
        } else {
          dw = h * mRatio
          dx = (w - dw) / 2
        }
        offCtx.drawImage(media, dx, dy, dw, dh)
        offCtx.filter = 'none'

        const imgData = offCtx.getImageData(0, 0, w, h).data
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        ctx.save()
        ctx.scale(dpr, dpr)

        const radius = pixelSize / 2
        const mouse = mousePosRef.current
        const mouseInfluenceDist = 40

        for (let y = 0; y < h; y += pixelSize) {
          for (let x = 0; x < w; x += pixelSize) {
            const cx = Math.min(Math.floor(x + radius), w - 1)
            const cy = Math.min(Math.floor(y + radius), h - 1)
            const i = (cy * w + cx) * 4
            const r = imgData[i]
            const g = imgData[i + 1]
            const b = imgData[i + 2]
            const a = imgData[i + 3]

            if (a === 0) continue

            let currentR = r
            let currentG = g
            let currentB = b

            if (colorMode === 'greyscale') {
              const grey = Math.round(0.299 * r + 0.587 * g + 0.114 * b)
              currentR = currentG = currentB = grey
            } else if (colorMode === 'palette') {
              let bestIdx = 0
              let bestDist = Infinity
              for (let p = 0; p < paletteRgb.length; p++) {
                const dist = colorDistSq(r, g, b, paletteRgb[p].r, paletteRgb[p].g, paletteRgb[p].b)
                if (dist < bestDist) {
                  bestDist = dist
                  bestIdx = p
                }
              }
              const palColor = paletteRgb[bestIdx]
              currentR = palColor.r
              currentG = palColor.g
              currentB = palColor.b
            }

            let scaleFactor = 0.9
            let skipDraw = false
            if (interactive && mouse.x > 0) {
              const distToMouse = Math.hypot(x + radius - mouse.x, y + radius - mouse.y)
              if (distToMouse < mouseInfluenceDist) {
                const infl = 1 - distToMouse / mouseInfluenceDist
                scaleFactor = 0.9 + infl * 0.45

                // Efecto de distorsión: 50% se vuelven café, 50% mantienen su color original
                if (Math.random() > 0.5) {
                  // Color cafecito/plum (#684959)
                  currentR = 104
                  currentG = 73
                  currentB = 89
                }
              }
            }

            if (skipDraw) continue

            const fill = `rgba(${currentR},${currentG},${currentB},${a / 255})`
            ctx.fillStyle = fill
            const currentRadius = radius * scaleFactor

            if (shapeMode === 'circles') {
              ctx.beginPath()
              ctx.arc(x + radius, y + radius, currentRadius, 0, Math.PI * 2)
              ctx.fill()
            } else if (shapeMode === 'squares') {
              const size = pixelSize * scaleFactor
              const offset = (pixelSize - size) / 2
              ctx.fillRect(x + offset, y + offset, size, size)
            } else if (shapeMode === 'octagons') {
              drawOctagon(ctx, x + radius, y + radius, currentRadius)
            } else if (shapeMode === 'small-circles-squares') {
              const isSq = (Math.floor(x / pixelSize) + Math.floor(y / pixelSize)) % 2 === 0
              if (isSq) {
                const size = pixelSize * scaleFactor * 0.85
                const offset = (pixelSize - size) / 2
                ctx.fillRect(x + offset, y + offset, size, size)
              } else {
                ctx.beginPath()
                ctx.arc(x + radius, y + radius, currentRadius * 0.7, 0, Math.PI * 2)
                ctx.fill()
              }
            }
          }
        }
        ctx.restore()
      }

      animFrameIdRef.current = requestAnimationFrame(render)
    }

    animFrameIdRef.current = requestAnimationFrame(render)

    return () => {
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current)
      if (resizeTimeout) clearTimeout(resizeTimeout)
      if (resizeObserver) resizeObserver.disconnect()
      window.removeEventListener('resize', updateDimensions)
      if (interactive) {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseleave', handleMouseLeave)
      }
      if (videoEl) {
        videoEl.pause()
        videoEl.src = ''
      }
    }
  }, [src, pixelSize, shapeMode, colorMode, palette, contrast, lightness, interactive])

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        zIndex: -1,
        pointerEvents: 'none',
        overflow: 'hidden',
        ...style,
      }}
      className={className}
    >
      <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
      {overlayOpacity > 0 && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: `rgba(0, 0, 0, ${overlayOpacity})`,
            backdropFilter: overlayBlur > 0 ? `blur(${overlayBlur}px)` : 'none',
            WebkitBackdropFilter: overlayBlur > 0 ? `blur(${overlayBlur}px)` : 'none',
          }}
        />
      )}
    </div>
  )
}

export default PixelCanvasBackground
