import { afterEach, describe, it, expect, vi } from 'vitest'

import { API_URL } from './api'
import {
  DEMO_SHOCKS,
  LiveApiError,
  esperarContrafactual,
  esperarOracle,
  getCounterfactual,
  getOracle,
  shockLive,
  tickLive,
} from './live'

function respuesta(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function error(p: Promise<unknown>): Promise<LiveApiError> {
  try {
    await p
  } catch (e) {
    if (e instanceof LiveApiError) return e
    throw e
  }
  throw new Error('no truena')
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('cliente live', () => {
  it('manda el tick como JSON al backend', async () => {
    const fetchMock = vi.fn(async () => respuesta(200, { minute: 1 }))
    vi.stubGlobal('fetch', fetchMock)
    await tickLive('live-1', 2)
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_URL}/live/tick`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ session_id: 'live-1', minutes: 2 }),
      })
    )
  })

  it('el delay del demo va sin duración, con slip_min, y acepta un order_id', async () => {
    expect(DEMO_SHOCKS.delay).toEqual({ shock_type: 'delay', slip_min: 15 })
    const fetchMock = vi.fn(async () => respuesta(200, { shock: {}, snapshot: {} }))
    vi.stubGlobal('fetch', fetchMock)
    await shockLive('live-1', DEMO_SHOCKS.delay)
    await shockLive('live-1', { shock_type: 'delay', slip_min: 10, order_id: 'o_059' })
    const cuerpos = fetchMock.mock.calls.map(
      (c) => JSON.parse((c as unknown as [string, RequestInit])[1].body as string) as unknown
    )
    expect(cuerpos).toEqual([
      { session_id: 'live-1', shock_type: 'delay', slip_min: 15 },
      { session_id: 'live-1', shock_type: 'delay', slip_min: 10, order_id: 'o_059' },
    ])
  })

  it('un 409 truena con el detail del backend y su status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => respuesta(409, { detail: 'la sesion live-1 ya no corre (ended)' }))
    )
    const e = await error(tickLive('live-1'))
    expect(e.status).toBe(409)
    expect(e.message).toBe('la sesion live-1 ya no corre (ended)')
  })

  it('un 422 de pydantic junta los mensajes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        respuesta(422, {
          detail: [{ loc: ['body', 'minutes'], msg: 'Input should be less than or equal to 10' }],
        })
      )
    )
    const e = await error(tickLive('live-1', 50))
    expect(e.status).toBe(422)
    expect(e.message).toContain('less than or equal to 10')
  })

  it('sin red truena con status 0 y dice a dónde intentó llegar', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      })
    )
    const e = await error(tickLive('live-1'))
    expect(e.status).toBe(0)
    expect(e.message).toBe(`Can't reach the live backend at ${API_URL}`)
  })

  const reporte = {
    session_id: 'live-2005-ab12',
    seed: 2005,
    money_skips: {},
    safety_skips: {},
    capacity_skips: 0,
    top: [],
  }
  const calculando = { status: 'computing', session_id: 'live-2005-ab12', seed: 2005 }

  it('pide el contrafactual de la sesión por GET; 202 es "todavía no"', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respuesta(202, calculando))
      .mockResolvedValueOnce(respuesta(200, reporte))
    vi.stubGlobal('fetch', fetchMock)
    expect(await getCounterfactual('live-2005-ab12')).toBeNull()
    expect(await getCounterfactual('live-2005-ab12')).toEqual(reporte)
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_URL}/live/counterfactual/live-2005-ab12`,
      expect.objectContaining({ method: 'GET' })
    )
  })

  it('un contrafactual con otra forma o sin session_id truena en vez de pintarse a medias', async () => {
    const sinSesion = { ...reporte, session_id: undefined }
    for (const cuerpo of [{ seed: 2005 }, sinSesion]) {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => respuesta(200, cuerpo))
      )
      const e = await error(getCounterfactual('live-2005-ab12'))
      expect(e.message).toMatch(/counterfactual/i)
    }
  })

  it('esperarContrafactual pregunta hasta que está listo', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(respuesta(202, calculando))
      .mockResolvedValueOnce(respuesta(202, calculando))
      .mockResolvedValueOnce(respuesta(200, reporte))
    vi.stubGlobal('fetch', fetchMock)
    const final = await esperarContrafactual('live-2005-ab12', () => true, 0)
    expect(final).toEqual({ status: 'ready', report: reporte })
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('esperarContrafactual dice la falla del backend en vez de quedarse calculando', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => respuesta(500, { detail: 're-simulation failed with ValueError: x' }))
    )
    const final = await esperarContrafactual('live-2005-ab12', () => true, 0)
    expect(final).toEqual({ status: 'failed', message: 're-simulation failed with ValueError: x' })
  })

  it('esperarContrafactual suelta la respuesta si la sesión ya no es la vigente', async () => {
    let vigente = true
    const fetchMock = vi.fn(async () => {
      vigente = false // otro Start mientras el backend calculaba
      return respuesta(200, reporte)
    })
    vi.stubGlobal('fetch', fetchMock)
    expect(await esperarContrafactual('live-2005-ab12', () => vigente, 0)).toBeNull()
  })

  it('Oracle se consulta después del cierre; 202 conserva el marcador en cálculo', async () => {
    const oracle = {
      session_id: 'live-2005-ab12',
      seed: 2005,
      earnings_mxn: 281,
      gross_earnings_mxn: 310,
      fuel_cost_mxn: 29,
      deliveries: 6,
      source: 'AgendaOracle',
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        respuesta(202, { status: 'computing', session_id: oracle.session_id, seed: 2005 })
      )
      .mockResolvedValueOnce(respuesta(200, oracle))
    vi.stubGlobal('fetch', fetchMock)
    expect(await getOracle(oracle.session_id)).toBeNull()
    expect(await getOracle(oracle.session_id)).toEqual(oracle)
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_URL}/live/oracle/${oracle.session_id}`,
      expect.objectContaining({ method: 'GET' })
    )
  })

  it('esperarOracle entrega el origen real del resultado, no una cifra disfrazada', async () => {
    const oracle = {
      session_id: 'live-2005-ab12',
      seed: 2005,
      earnings_mxn: 260,
      gross_earnings_mxn: 280,
      fuel_cost_mxn: 20,
      deliveries: 5,
      source: 'OurAgent',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => respuesta(200, oracle))
    )
    expect(await esperarOracle(oracle.session_id, () => true, 0)).toEqual({
      status: 'ready',
      report: oracle,
    })
  })
})
