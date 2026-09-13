// La voz de Nuez en el navegador. Sin UI: son dos funciones para que quien maneje
// las decisiones las llame.
//
//   import { say, listen } from './voice/nuez'
//   say('Take it.')                  // habla; las frases se encolan, no se pisan
//   callar()                         // descarta la cola (pausa, seek)
//   const texto = await listen(4000) // graba 4 s del micro y devuelve lo que dijo
//
// El audio lo genera el backend (la llave nunca llega aqui): GET /api/voice/say?text=...
// Los navegadores bloquean audio hasta un gesto del usuario: la primera `say` debe
// venir de un click (o llamar `unlock()` en el click de "Start shift").

import { API_URL } from '../lib/api'

/** URL que reproduce una frase. Sirve tal cual en `<audio src>`. */
export function sayUrl(text: string, apiUrl: string = API_URL): string {
  const base = `${apiUrl}/api/voice/say?text=${encodeURIComponent(text.trim())}`
  return elevenLabsLang !== 'en' ? `${base}&lang=${elevenLabsLang}` : base
}

/** Quién sonó la última frase. `browser` = ElevenLabs no respondió y habló el navegador. */
export type FuenteVoz = 'elevenlabs' | 'browser'

let cola: Promise<void> = Promise.resolve()
let desbloqueado = false
let generacion = 0
let elevenLabsLang = 'en'
let browserLang = 'en-US'
let langListeners: Array<() => void> = []

export function setVoiceLanguage(elLang: string, bLang: string) {
  elevenLabsLang = elLang
  browserLang = bLang
  langListeners.forEach((cb) => cb())
}

export function getVoiceLanguage() {
  return { elLang: elevenLabsLang, bLang: browserLang }
}

export function onVoiceLanguage(cb: () => void) {
  langListeners.push(cb)
  return () => { langListeners = langListeners.filter((l) => l !== cb) }
}
let sonando: { audio: HTMLAudioElement; soltar: () => void } | null = null
const oyentes = new Set<(f: FuenteVoz) => void>()

/** Avisa cada vez que cambia de ElevenLabs al navegador o de regreso. Devuelve cómo dejar de oír. */
export function onFuente(cb: (f: FuenteVoz) => void): () => void {
  oyentes.add(cb)
  return () => oyentes.delete(cb)
}

function avisar(f: FuenteVoz): void {
  oyentes.forEach((cb) => cb(f))
}

/** Llamar desde un click para que las frases posteriores puedan sonar solas. */
export function unlock(): void {
  if (desbloqueado) return
  const a = new Audio()
  a.muted = true
  void a.play().catch(() => undefined)
  desbloqueado = true
}

/** Voz del sistema. Sin red y sin cuota: el seguro para que el demo nunca quede mudo. */
function hablarNavegador(text: string, lang: string): Promise<void> {
  if (typeof speechSynthesis === 'undefined') return Promise.resolve()
  return new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = lang
    u.rate = 1.05
    u.onend = () => resolve()
    u.onerror = () => resolve()
    speechSynthesis.speak(u)
  })
}

function reproducir(text: string, lang: string): Promise<void> {
  return new Promise((resolve) => {
    const audio = new Audio(sayUrl(text))
    // `pause()` no dispara onended: sin esto, callar() dejaría la cola trabada para siempre.
    sonando = { audio, soltar: resolve }
    audio.preload = 'auto'
    audio.onplaying = () => avisar('elevenlabs')
    audio.onended = () => resolve()
    // 502 del backend (llave rechazada, sin cuota, sin red y sin cache): habla el navegador.
    // El navegador avisa dos veces (onerror y play() rechazado); se cae una sola vez, y la
    // promesa espera a que la voz del navegador termine para que las frases no se amontonen.
    let cayo = false
    const caer = () => {
      if (cayo || sonando?.audio !== audio) return // ya cayó, o callar() la descartó
      cayo = true
      avisar('browser')
      void hablarNavegador(text, lang).then(resolve)
    }
    audio.onerror = caer
    void audio.play().catch((e: unknown) => {
      if (e instanceof DOMException && e.name === 'NotSupportedError') caer()
      else if (!cayo) resolve() // autoplay bloqueado o pause() de callar(): no hay nada que esperar
    })
  })
}

/**
 * Habla una frase. Las frases se encolan en orden; la promesa resuelve al terminar esa frase.
 * `lang` es el idioma de la voz del navegador si ElevenLabs no responde (/live pasa en-US).
 */
export function say(text: string, { lang }: { lang?: string } = {}): Promise<void> {
  const t = text.trim()
  if (!t) return Promise.resolve()
  const mia = generacion
  const actualLang = lang ?? browserLang
  const turno = cola.then(() => (mia === generacion ? reproducir(t, actualLang) : undefined))
  cola = turno.catch(() => undefined)
  return turno
}

/** Calla lo que suena y descarta lo encolado. Para pausa, cambio de minuto a mano o de seed. */
export function callar(): void {
  generacion++
  if (sonando) {
    sonando.audio.onerror = null // que el pause no se lea como falla y hable el navegador
    sonando.audio.pause()
    sonando.soltar()
    sonando = null
  }
  if (typeof speechSynthesis !== 'undefined') speechSynthesis.cancel()
}

/** Calienta la cache del backend con frases que se van a decir, sin sonarlas. */
// Una por una y leyendo el cuerpo: el backend escribe la cache al terminar el stream, y el
// plan free de ElevenLabs rechaza (429) si se le mandan muchas a la vez. Una llamada nueva
// (otro seed) cancela a la anterior: nunca hay dos recorridos pidiendo frases al mismo tiempo.
let recorrido = 0

export async function prefetch(texts: string[]): Promise<void> {
  const mio = ++recorrido
  for (const t of texts) {
    if (mio !== recorrido) return
    try {
      const res = await fetch(sayUrl(t))
      await res.arrayBuffer()
      if (!res.ok) return // llave rechazada o sin cuota: las demás fallarían igual
    } catch {
      return // sin red: el demo usará la cache que ya haya o la voz del navegador
    }
  }
}

/** Graba `ms` milisegundos del microfono y devuelve la transcripcion. */
export async function listen(ms = 4000, apiUrl: string = API_URL): Promise<string> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const rec = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
  const partes: BlobPart[] = []
  rec.ondataavailable = (e) => partes.push(e.data)

  const terminado = new Promise<Blob>((resolve) => {
    rec.onstop = () => resolve(new Blob(partes, { type: 'audio/webm' }))
  })
  rec.start()
  await new Promise((r) => setTimeout(r, ms))
  rec.stop()
  stream.getTracks().forEach((tr) => tr.stop())

  const form = new FormData()
  form.append('file', await terminado, 'clip.webm')
  const res = await fetch(`${apiUrl}/api/voice/listen`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`listen failed: ${res.status}`)
  const j = (await res.json()) as { text: string }
  return j.text
}
