import React, { useEffect, useRef } from 'react';

export interface PixelCanvasBackgroundProps {
  /** Ruta del archivo de video o imagen (por defecto usa la configurada en FrontHelp) */
  src?: string;
  pixelSize?: number;
  shapeMode?: 'circles' | 'squares' | 'octagons' | 'small-circles-squares' | 'random';
  showGrid?: boolean;
  colorMode?: 'palette' | 'full' | 'greyscale';
  palette?: string[];
  contrast?: number;
  lightness?: number;
  interactive?: boolean;
  overlayOpacity?: number;
  overlayBlur?: number;
  className?: string;
  style?: React.CSSProperties;
}

// ── Configuraciones por defecto exportadas desde FrontHelp ──────────────────
const DEFAULT_VIDEO_SRC = '/background.mp4';
const DEFAULT_PIXEL_SIZE = 5;
const DEFAULT_SHAPE_MODE = 'random';
const DEFAULT_COLOR_MODE = 'greyscale';
const DEFAULT_PALETTE = [
  "#FF4500",
  "#0000CD",
  "#00C800",
  "#FFD700"
];
const DEFAULT_CONTRAST = 100;
const DEFAULT_LIGHTNESS = 100;

const hexToRgb = (hex: string) => {
  const clean = hex.replace('#', '');
  const bigint = parseInt(clean, 16);
  if (clean.length === 3) {
    const r = (bigint >> 8) & 15;
    const g = (bigint >> 4) & 15;
    const b = bigint & 15;
    return { r: (r << 4) | r, g: (g << 4) | g, b: (b << 4) | b };
  }
  return {
    r: (bigint >> 16) & 255,
    g: (bigint >> 8) & 255,
    b: bigint & 255,
  };
};

const colorDistSq = (r1: number, g1: number, b1: number, r2: number, g2: number, b2: number) =>
  (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2;

const drawOctagon = (ctx: CanvasRenderingContext2D, cx: number, cy: number, r: number) => {
  ctx.beginPath();
  for (let i = 0; i < 8; i++) {
    const angle = (i * Math.PI) / 4 + Math.PI / 8;
    const vx = cx + r * Math.cos(angle);
    const vy = cy + r * Math.sin(angle);
    if (i === 0) ctx.moveTo(vx, vy);
    else ctx.lineTo(vx, vy);
  }
  ctx.closePath();
  ctx.fill();
};

const getPseudoRandomShape = (x: number, y: number): 'circles' | 'squares' | 'octagons' => {
  const shapes: ('circles' | 'squares' | 'octagons')[] = ['circles', 'squares', 'octagons'];
  return shapes[(Math.floor(x) * 17 + Math.floor(y) * 31) % 3];
};

export const PixelCanvasBackground: React.FC<PixelCanvasBackgroundProps> = ({
  src = DEFAULT_VIDEO_SRC,
  pixelSize = DEFAULT_PIXEL_SIZE,
  shapeMode = DEFAULT_SHAPE_MODE,
  showGrid = false,
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
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mediaRef = useRef<HTMLVideoElement | HTMLImageElement | null>(null);
  const offscreenRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameIdRef = useRef<number | null>(null);
  const mousePosRef = useRef<{ x: number; y: number }>({ x: -1000, y: -1000 });

  useEffect(() => {
    const isVideo = /\.(mp4|webm|ogg|mov)(\?.*)?$/i.test(src);
    let videoEl: HTMLVideoElement | null = null;
    let imageEl: HTMLImageElement | null = null;
    let isReady = false;

    if (isVideo) {
      videoEl = document.createElement('video');
      videoEl.src = src;
      videoEl.crossOrigin = 'anonymous';
      videoEl.loop = true;
      videoEl.muted = true;
      videoEl.playsInline = true;
      videoEl.autoplay = true;
      videoEl.onloadeddata = () => { isReady = true; };
      videoEl.play().catch(() => {});
      mediaRef.current = videoEl;
    } else {
      imageEl = new Image();
      imageEl.crossOrigin = 'anonymous';
      imageEl.src = src;
      imageEl.onload = () => { isReady = true; };
      mediaRef.current = imageEl;
    }

    const offscreen = document.createElement('canvas');
    offscreenRef.current = offscreen;
    const offCtx = offscreen.getContext('2d', { willReadFrequently: true });

    const canvas = canvasRef.current;
    if (!canvas || !offCtx) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const paletteRgb = palette.map(hexToRgb);

    const updateDimensions = () => {
      const parent = canvas.parentElement;
      const w = parent && parent.clientWidth > 0 ? parent.clientWidth : window.innerWidth;
      const h = parent && parent.clientHeight > 0 ? parent.clientHeight : window.innerHeight;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = '100%';
      canvas.style.height = '100%';

      offscreen.width = w;
      offscreen.height = h;
    };
    updateDimensions();
    window.addEventListener('resize', updateDimensions);

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mousePosRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    };
    const handleMouseLeave = () => {
      mousePosRef.current = { x: -1000, y: -1000 };
    };

    if (interactive) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseleave', handleMouseLeave);
    }

    const render = () => {
      const media = mediaRef.current;
      const w = offscreen.width;
      const h = offscreen.height;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      const canDraw = isReady && media && (
        (isVideo && videoEl && videoEl.readyState >= 2) ||
        (!isVideo && imageEl && imageEl.complete)
      );

      if (canDraw && media) {
        const mw = (media as HTMLVideoElement).videoWidth || (media as HTMLImageElement).naturalWidth || w;
        const mh = (media as HTMLVideoElement).videoHeight || (media as HTMLImageElement).naturalHeight || h;

        offCtx.clearRect(0, 0, w, h);
        offCtx.filter = `contrast(${contrast}%) brightness(${lightness}%)`;

        const mRatio = mw / mh;
        const cRatio = w / h;
        let dw = w, dh = h, dx = 0, dy = 0;
        if (cRatio > mRatio) {
          dh = w / mRatio;
          dy = (h - dh) / 2;
        } else {
          dw = h * mRatio;
          dx = (w - dw) / 2;
        }
        offCtx.drawImage(media, dx, dy, dw, dh);
        offCtx.filter = 'none';

        const imgData = offCtx.getImageData(0, 0, w, h).data;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.save();
        ctx.scale(dpr, dpr);

        const radius = pixelSize / 2;
        const mouse = mousePosRef.current;
        const mouseInfluenceDist = 120;

        for (let y = 0; y < h; y += pixelSize) {
          for (let x = 0; x < w; x += pixelSize) {
            const cx = Math.min(Math.floor(x + radius), w - 1);
            const cy = Math.min(Math.floor(y + radius), h - 1);
            const i = (cy * w + cx) * 4;
            const r = imgData[i];
            const g = imgData[i + 1];
            const b = imgData[i + 2];
            const a = imgData[i + 3];

            if (a === 0) continue;

            let fill = `rgba(${r},${g},${b},${a / 255})`;
            if (colorMode === 'greyscale') {
              const grey = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
              fill = `rgba(${grey},${grey},${grey},${a / 255})`;
            } else if (colorMode === 'palette') {
              let bestIdx = 0;
              let bestDist = Infinity;
              for (let p = 0; p < paletteRgb.length; p++) {
                const dist = colorDistSq(r, g, b, paletteRgb[p].r, paletteRgb[p].g, paletteRgb[p].b);
                if (dist < bestDist) {
                  bestDist = dist;
                  bestIdx = p;
                }
              }
              const palColor = paletteRgb[bestIdx];
              fill = `rgba(${palColor.r},${palColor.g},${palColor.b},${a / 255})`;
            }

            let scaleFactor = 0.9;
            if (interactive && mouse.x > 0) {
              const distToMouse = Math.hypot(x + radius - mouse.x, y + radius - mouse.y);
              if (distToMouse < mouseInfluenceDist) {
                const infl = 1 - distToMouse / mouseInfluenceDist;
                scaleFactor = 0.9 + infl * 0.45;
              }
            }

            ctx.fillStyle = fill;
            const currentRadius = radius * scaleFactor;

            const resolvedShape = shapeMode === 'random' ? getPseudoRandomShape(x, y) : shapeMode;

            if (resolvedShape === 'circles') {
              ctx.beginPath();
              ctx.arc(x + radius, y + radius, currentRadius, 0, Math.PI * 2);
              ctx.fill();
            } else if (resolvedShape === 'squares') {
              const size = pixelSize * scaleFactor;
              const offset = (pixelSize - size) / 2;
              ctx.fillRect(x + offset, y + offset, size, size);
            } else if (resolvedShape === 'octagons') {
              drawOctagon(ctx, x + radius, y + radius, currentRadius);
            } else if (resolvedShape === 'small-circles-squares') {
              const isSq = (Math.floor(x / pixelSize) + Math.floor(y / pixelSize)) % 2 === 0;
              if (isSq) {
                const size = pixelSize * scaleFactor * 0.85;
                const offset = (pixelSize - size) / 2;
                ctx.fillRect(x + offset, y + offset, size, size);
              } else {
                ctx.beginPath();
                ctx.arc(x + radius, y + radius, currentRadius * 0.7, 0, Math.PI * 2);
                ctx.fill();
              }
            }
          }
        }

        if (showGrid) {
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
          ctx.lineWidth = 1;
          for (let gx = 0; gx <= w; gx += pixelSize * 2) {
            ctx.beginPath();
            ctx.moveTo(gx, 0);
            ctx.lineTo(gx, h);
            ctx.stroke();
          }
          for (let gy = 0; gy <= h; gy += pixelSize * 2) {
            ctx.beginPath();
            ctx.moveTo(0, gy);
            ctx.lineTo(w, gy);
            ctx.stroke();
          }
        }
        ctx.restore();
      }

      animFrameIdRef.current = requestAnimationFrame(render);
    };

    animFrameIdRef.current = requestAnimationFrame(render);

    return () => {
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
      window.removeEventListener('resize', updateDimensions);
      if (interactive) {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseleave', handleMouseLeave);
      }
      if (videoEl) {
        videoEl.pause();
        videoEl.src = '';
      }
    };
  }, [src, pixelSize, shapeMode, colorMode, palette, contrast, lightness, interactive]);

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 0,
        pointerEvents: 'none',
        overflow: 'hidden',
        ...style,
      }}
      className={className}
    >
      <canvas
        ref={canvasRef}
        style={{ display: 'block', width: '100%', height: '100%' }}
      />
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
  );
};

export default PixelCanvasBackground;
