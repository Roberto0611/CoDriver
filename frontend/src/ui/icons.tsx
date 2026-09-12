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
}
