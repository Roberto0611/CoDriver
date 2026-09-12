// La voz de Nuez en el navegador. Sin UI: son dos funciones para que quien maneje
// las decisiones las llame.
//
//   import { say, listen } from './voice/nuez'
//   say(decision.razon)              // habla; las frases se encolan, no se pisan
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

let cola: Promise<void> = Promise.resolve()
let desbloqueado = false

/** Llamar desde un click para que las frases posteriores puedan sonar solas. */
export function unlock(): void {
  if (desbloqueado) return
  const a = new Audio()
  a.muted = true
  void a.play().catch(() => undefined)
  desbloqueado = true
}

function reproducir(url: string): Promise<void> {
  return new Promise((resolve) => {
    const audio = new Audio(url)
    audio.preload = 'auto'
    audio.onended = () => resolve()
    audio.onerror = () => resolve() // una frase que falla no traba la cola
    void audio.play().catch(() => resolve())
  })
}

/** Habla una frase. Las frases se encolan en orden; la promesa resuelve al terminar esa frase. */
export function say(text: string): Promise<void> {
  const t = text.trim()
  if (!t) return Promise.resolve()
  const turno = cola.then(() => reproducir(sayUrl(t)))
  cola = turno.catch(() => undefined)
  return turno
}

/** Calienta la cache del backend con frases que se van a decir, sin sonarlas. */
export async function prefetch(texts: string[]): Promise<void> {
  await Promise.all(texts.map((t) => fetch(sayUrl(t), { method: 'GET' }).catch(() => undefined)))
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
