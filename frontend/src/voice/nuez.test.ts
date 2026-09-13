import { afterEach, describe, expect, it, vi } from 'vitest'
import { callar, prefetch, say, sayUrl } from './nuez'

describe('sayUrl', () => {
  it('points at the backend voice route and encodes the text', () => {
    expect(sayUrl("Skip it. That's 22 minutes & 26 back.", 'http://api')).toBe(
      "http://api/api/voice/say?text=Skip%20it.%20That's%2022%20minutes%20%26%2026%20back."
    )
  })

  it('trims surrounding whitespace so the backend cache key matches', () => {
    expect(sayUrl('  Skip it. ', 'http://api')).toBe('http://api/api/voice/say?text=Skip%20it.')
  })
})

/** Un <audio> cuyo backend responde 502: como el navegador, dispara onerror y rechaza play(). */
class AudioQueFalla {
  onerror: (() => void) | null = null
  onended: (() => void) | null = null
  onplaying: (() => void) | null = null
  preload = ''
  play(): Promise<void> {
    queueMicrotask(() => this.onerror?.())
    return Promise.reject(new DOMException('no source', 'NotSupportedError'))
  }
  pause(): void {}
}

class Utterance {
  lang = ''
  rate = 1
  onend: (() => void) | null = null
  onerror: (() => void) | null = null
  text: string
  constructor(text: string) {
    this.text = text
  }
}

const tick = () => new Promise((r) => setTimeout(r, 0))

afterEach(() => {
  callar()
  vi.unstubAllGlobals()
})

describe('say with ElevenLabs down', () => {
  it('does not finish until the browser voice finishes speaking', async () => {
    const dichas: Utterance[] = []
    vi.stubGlobal('Audio', AudioQueFalla)
    vi.stubGlobal('SpeechSynthesisUtterance', Utterance)
    vi.stubGlobal('speechSynthesis', { speak: (u: Utterance) => dichas.push(u), cancel() {} })

    let termino = false
    const promesa = say('Take it.').then(() => {
      termino = true
    })
    await tick()
    await tick()

    expect(dichas.map((u) => u.text)).toEqual(['Take it.'])
    expect(termino).toBe(false) // resolving here lets lines pile up at 4x

    dichas[0].onend?.()
    await promesa
    expect(termino).toBe(true)
  })

  it('the browser voice is en-US by default and takes the lang option (Spanish reasons on /live)', async () => {
    const dichas: Utterance[] = []
    vi.stubGlobal('Audio', AudioQueFalla)
    vi.stubGlobal('SpeechSynthesisUtterance', Utterance)
    vi.stubGlobal('speechSynthesis', {
      speak: (u: Utterance) => {
        dichas.push(u)
        queueMicrotask(() => u.onend?.())
      },
      cancel() {},
    })

    await say('Take it.')
    await say('Zona marcada.', { lang: 'es-MX' })

    expect(dichas.map((u) => [u.text, u.lang])).toEqual([
      ['Take it.', 'en-US'],
      ['Zona marcada.', 'es-MX'],
    ])
  })
})

describe('prefetch', () => {
  it('a new call cancels the previous one so two never fetch at once', async () => {
    const pedidas: string[] = []
    const pendientes: Array<() => void> = []
    vi.stubGlobal('fetch', (url: string) => {
      pedidas.push(decodeURIComponent(url.split('text=')[1]))
      return new Promise((resolve) => {
        pendientes.push(() => resolve({ ok: true, arrayBuffer: async () => new ArrayBuffer(0) }))
      })
    })

    const viejo = prefetch(['a', 'b', 'c'])
    await tick()
    const nuevo = prefetch(['z'])
    await tick()
    while (pendientes.length) {
      pendientes.shift()?.()
      await tick()
    }
    await Promise.all([viejo, nuevo])

    expect(pedidas).toContain('z')
    expect(pedidas).not.toContain('b')
  })
})
