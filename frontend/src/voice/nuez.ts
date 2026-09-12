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
  return `${apiUrl}/api/voice/say?text=${encodeURIComponent(text.trim())}`
}

/** Quién sonó la última frase. `browser` = ElevenLabs no respondió y habló el navegador. */
export type FuenteVoz = 'elevenlabs' | 'browser'

let cola: Promise<void> = Promise.resolve()
let desbloqueado = false
let generacion = 0
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
function hablarNavegador(text: string): Promise<void> {
  if (typeof speechSynthesis === 'undefined') return Promise.resolve()
  return new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-US'
    u.rate = 1.05
    u.onend = () => resolve()
    u.onerror = () => resolve()
    speechSynthesis.speak(u)
  })
}

function reproducir(text: string): Promise<void> {
  return new Promise((resolve) => {
    const audio = new Audio(sayUrl(text))
    // `pause()` no dispara onended: sin esto, callar() dejaría la cola trabada para siempre.
    sonando = { audio, soltar: resolve }
    audio.preload = 'auto'
    audio.onplaying = () => avisar('elevenlabs')
    audio.onended = () => resolve()
    // 502 del backend (llave rechazada, sin cuota, sin red y sin cache): habla el navegador.
    audio.onerror = () => {
      avisar('browser')
      void hablarNavegador(text).then(resolve)
    }
    void audio.play().catch(() => resolve())
  })
}

/** Habla una frase. Las frases se encolan en orden; la promesa resuelve al terminar esa frase. */
export function say(text: string): Promise<void> {
  const t = text.trim()
  if (!t) return Promise.resolve()
  const mia = generacion
  const turno = cola.then(() => (mia === generacion ? reproducir(t) : undefined))
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
// plan free de ElevenLabs rechaza (429) si se le mandan muchas a la vez.
export async function prefetch(texts: string[]): Promise<void> {
  for (const t of texts) {
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
