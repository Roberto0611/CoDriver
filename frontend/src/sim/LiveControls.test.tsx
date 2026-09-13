import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { horaDeRegreso } from '../lib/countersCopy'
import { GEMINI_IDLE } from '../lib/gemini-status'
import type { LiveStartParams } from '../lib/live'
import { LiveControls, LiveStartForm } from './LiveControls'

const PARAMS: LiveStartParams = {
  seed: 2005,
  duracion_min: 510,
  hora_inicio: 14,
  vehiculo: 'moto',
  ancla: 4,
  margen_min: 10,
}

const nada = () => undefined

describe('turno de 8.5 h en /live', () => {
  it('el formulario ofrece 2 h, 8 h y 8.5 h, con 8.5 h elegible', () => {
    const html = renderToStaticMarkup(
      <LiveStartForm
        params={PARAMS}
        zones={[]}
        rehearsal={null}
        disabled={false}
        onChange={nada}
        onNewSeed={nada}
        onStart={nada}
      />
    )
    expect(html).toContain('<option value="120">2 h</option>')
    expect(html).toContain('<option value="480">8 h</option>')
    expect(html).toContain('<option value="510" selected="">8.5 h</option>')
  })

  it('la píldora termina a las 22:30 y el regreso es a las 22:20 con margen 10', () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <LiveControls
          gemini={GEMINI_IDLE}
          phase="idle"
          hasSession={false}
          startHour={14}
          minute={0}
          duration={510}
          speedIdx={0}
          voice={false}
          voiceSource="elevenlabs"
          pending={null}
          onPlayPause={nada}
          onSpeed={nada}
          onVoice={nada}
          onShock={nada}
          onEnd={nada}
          onNewShift={nada}
        />
      </MemoryRouter>
    )
    expect(html).toContain('<span>14:00</span><span>22:30</span>')
    // "Back by" es fin del turno menos el margen, igual que 15:50 en uno de 2 h.
    expect(horaDeRegreso({ hora_inicio: 14, duracion_min: 510, margen_min: 10 })).toBe('22:20')
  })
})
