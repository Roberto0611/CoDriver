import { describe, it, expect } from 'vitest'
import {
  consultarGemini,
  esperaTrasConsulta,
  GEMINI_IDLE,
  mismaVista,
  POLL_MS,
  POLL_OFFLINE_MAX_MS,
  vistaGemini,
} from './gemini-status'

const NOTA = 'Rain in Centro, staying close is worth it.'

describe('vistaGemini', () => {
  it('sin turno → idle con el texto de "no live shift"', () => {
    const vista = vistaGemini({ active: false, degraded: false, strategy_note: null })
    expect(vista).toEqual(GEMINI_IDLE)
    expect(vista.label).toBe('Gemini: idle')
  })

  it('sin turno ignora una nota vieja', () => {
    expect(vistaGemini({ active: false, strategy_note: NOTA }).note).toBeNull()
  })

  it('turno vivo con estrategia de Gemini → active con su nota', () => {
    const vista = vistaGemini({
      active: true,
      degraded: false,
      strategy_source: 'gemini',
      strategy_note: NOTA,
    })
    expect(vista.state).toBe('active')
    expect(vista.label).toBe('Gemini: active')
    expect(vista.note).toBe(NOTA)
  })

  it('turno vivo y degradado → degraded, conserva la última nota', () => {
    const vista = vistaGemini({
      active: true,
      degraded: true,
      strategy_source: 'gemini_vieja',
      strategy_note: NOTA,
    })
    expect(vista.state).toBe('degraded')
    expect(vista.label).toBe('Gemini: down, using last strategy')
    expect(vista.note).toBe(NOTA)
  })

  it('degradado sin nota → placeholder de caído', () => {
    const vista = vistaGemini({ active: true, degraded: true, strategy_source: 'base_vieja' })
    expect(vista.note).toBeNull()
    expect(vista.placeholder).toMatch(/not answering/)
  })

  it('turno vivo antes de la primera respuesta (base) → idle, nunca active', () => {
    const vista = vistaGemini({ active: true, degraded: false, strategy_source: 'base' })
    expect(vista.state).toBe('idle')
    expect(vista.placeholder).toMatch(/Shift is live/)
  })

  it('suplente local (falso) → idle y sin su nota', () => {
    const vista = vistaGemini({
      active: true,
      degraded: false,
      strategy_source: 'falso',
      strategy_note: 'suplente local',
    })
    expect(vista.state).toBe('idle')
    expect(vista.note).toBeNull()
  })

  it('backend viejo sin strategy_source → idle', () => {
    expect(vistaGemini({ active: true, degraded: false }).state).toBe('idle')
  })

  it('nota en blanco → null', () => {
    const vista = vistaGemini({ active: true, strategy_source: 'gemini', strategy_note: '   ' })
    expect(vista.note).toBeNull()
  })

  it.each([null, undefined, 'ok', 42, [], {}])('forma desconocida %s → idle', (basura) => {
    expect(vistaGemini(basura)).toEqual(GEMINI_IDLE)
  })
})

describe('mismaVista', () => {
  it('misma forma aunque sea otro objeto → true', () => {
    expect(mismaVista(GEMINI_IDLE, { ...GEMINI_IDLE })).toBe(true)
  })

  it('cambia la nota → false', () => {
    const a = vistaGemini({ active: true, strategy_source: 'gemini', strategy_note: NOTA })
    const b = vistaGemini({ active: true, strategy_source: 'gemini', strategy_note: 'otra' })
    expect(mismaVista(a, b)).toBe(false)
  })

  it('cambia el estado → false', () => {
    const activo = vistaGemini({ active: true, strategy_source: 'gemini' })
    expect(mismaVista(activo, GEMINI_IDLE)).toBe(false)
  })
})

describe('esperaTrasConsulta', () => {
  it('backend vivo → cada POLL_MS', () => {
    expect(esperaTrasConsulta(0)).toBe(POLL_MS)
  })

  it('backend apagado → la espera se duplica con cada fallo seguido', () => {
    expect(esperaTrasConsulta(1)).toBe(POLL_MS * 2)
    expect(esperaTrasConsulta(2)).toBe(POLL_MS * 4)
    expect(esperaTrasConsulta(3)).toBe(POLL_MS * 8)
  })

  it('con el tope de un minuto, sin desbordarse', () => {
    expect(esperaTrasConsulta(5)).toBe(POLL_OFFLINE_MAX_MS)
    expect(esperaTrasConsulta(1000)).toBe(POLL_OFFLINE_MAX_MS)
  })
})

describe('consultarGemini', () => {
  const signal = new AbortController().signal

  it('llama a /shift/status del API_URL recibido', async () => {
    let pedida = ''
    const { view, reachable } = await consultarGemini(
      async (url) => {
        pedida = url
        return {
          ok: true,
          json: async () => ({ active: true, strategy_source: 'gemini', strategy_note: NOTA }),
        }
      },
      'http://api.test',
      signal
    )
    expect(pedida).toBe('http://api.test/shift/status')
    expect(view.state).toBe('active')
    expect(reachable).toBe(true)
  })

  it('backend vivo sin turno → idle pero alcanzable', async () => {
    const consulta = await consultarGemini(
      async () => ({ ok: true, json: async () => ({ active: false, degraded: false }) }),
      'http://api.test',
      signal
    )
    expect(consulta).toEqual({ view: GEMINI_IDLE, reachable: true })
  })

  it('backend apagado (fetch rechaza) → idle, sin lanzar', async () => {
    const consulta = await consultarGemini(
      async () => {
        throw new TypeError('Failed to fetch')
      },
      'http://api.test',
      signal
    )
    expect(consulta).toEqual({ view: GEMINI_IDLE, reachable: false })
  })

  it('HTTP de error → idle', async () => {
    const consulta = await consultarGemini(
      async () => ({ ok: false, json: async () => ({ active: true, strategy_source: 'gemini' }) }),
      'http://api.test',
      signal
    )
    expect(consulta).toEqual({ view: GEMINI_IDLE, reachable: false })
  })

  it('JSON roto → idle', async () => {
    const consulta = await consultarGemini(
      async () => ({
        ok: true,
        json: async () => {
          throw new SyntaxError('Unexpected token')
        },
      }),
      'http://api.test',
      signal
    )
    expect(consulta).toEqual({ view: GEMINI_IDLE, reachable: false })
  })
})
