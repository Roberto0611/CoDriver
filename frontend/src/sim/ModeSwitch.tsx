// Cambio entre el replay grabado (/sim) y el turno en vivo (/live), con el
// mismo control segmentado que la velocidad.

import { NavLink } from 'react-router-dom'

const MODOS = [
  { to: '/sim', label: 'Recorded replay' },
  { to: '/live', label: 'Live demo' },
] as const

export function ModeSwitch() {
  return (
    <nav className="mode-switch" aria-label="Mode">
      {MODOS.map((m) => (
        <NavLink
          key={m.to}
          to={m.to}
          end
          className={({ isActive }) => `speed-btn ${isActive ? 'is-active' : ''}`}
        >
          {m.label}
        </NavLink>
      ))}
    </nav>
  )
}
