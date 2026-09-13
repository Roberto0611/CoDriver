// Iconos: SVG en línea, un solo estilo (trazo 1.8, cuadrícula 24px, currentColor).
// Nunca emoji. Se agregan aquí, con el mismo estilo.

const stroke = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
} as const

export const Icon = {
  mark: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M7 9.5c0-2.5 2.2-4.5 5-4.5s5 2 5 4.5" />
      <path d="M5.5 9.5h13" />
      <path d="M6.5 9.5c0 5 2.5 8.5 5.5 9.5 3-1 5.5-4.5 5.5-9.5" />
      <path d="M12 5V3" />
    </svg>
  ),
  chevron: (
    <svg viewBox="0 0 24 24" {...stroke} strokeWidth={2}>
      <path d="M6 9l6 6 6-6" />
    </svg>
  ),
  route: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <circle cx="6" cy="19" r="2" />
      <circle cx="18" cy="5" r="2" />
      <path d="M8 19h5a4 4 0 0 0 0-8h-2a4 4 0 0 1 0-8h5" />
    </svg>
  ),
  pin: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M12 21s-6-5.3-6-10a6 6 0 0 1 12 0c0 4.7-6 10-6 10z" />
      <circle cx="12" cy="11" r="2" />
    </svg>
  ),
  map: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z" />
      <path d="M9 4v14" />
      <path d="M15 6v14" />
    </svg>
  ),
  play: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <polygon points="6 4 20 12 6 20 6 4" fill="currentColor" stroke="none" />
    </svg>
  ),
  pause: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <rect x="6" y="4" width="4" height="16" rx="1" fill="currentColor" stroke="none" />
      <rect x="14" y="4" width="4" height="16" rx="1" fill="currentColor" stroke="none" />
    </svg>
  ),
  stepBack: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M15 18l-6-6 6-6" />
      <path d="M9 6v12" />
    </svg>
  ),
  stepForward: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M9 18l6-6-6-6" />
      <path d="M15 6v12" />
    </svg>
  ),
  moto: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <circle cx="5" cy="17" r="3" />
      <circle cx="19" cy="17" r="3" />
      <path d="M5 14l3-7h4l3 7" />
      <path d="M8 7h8l3 10" />
    </svg>
  ),
  dollar: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M12 2v20" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
  shield: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  box: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M21 8l-9-5-9 5v8l9 5 9-5z" />
      <path d="M3 8l9 5 9-5" />
      <path d="M12 13v8" />
    </svg>
  ),
  skip: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M18 6L6 18" />
      <path d="M6 6l12 12" />
    </svg>
  ),
  accept: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M20 6L9 17l-5-5" />
    </svg>
  ),
  speed: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
  ),
  restaurant: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2" />
      <path d="M7 2v20" />
      <path d="M21 15V2v0a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7" />
    </svg>
  ),
  user: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
  voice: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M11 5L6 9H3v6h3l5 4V5z" />
      <path d="M15.5 8.5a5 5 0 0 1 0 7" />
      <path d="M18.5 5.5a9 9 0 0 1 0 13" />
    </svg>
  ),
  voiceOff: (
    <svg viewBox="0 0 24 24" {...stroke}>
      <path d="M11 5L6 9H3v6h3l5 4V5z" />
      <path d="M22 9l-6 6" />
      <path d="M16 9l6 6" />
    </svg>
  ),
}
