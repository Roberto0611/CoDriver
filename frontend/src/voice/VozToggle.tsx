// Botón de voz de la barra de tiempo. Mientras está encendido y el turno corre, Nuez dice
// en voz alta sus aceptaciones y sus rechazos por reglas duras (ver frases.ts).
//
// El click es a la vez el gesto que desbloquea el audio del navegador y el momento de
// calentar la cache con las frases de este turno: ensayado una vez con red, el demo suena
// igual sin wifi. Si ElevenLabs no responde, habla la voz del navegador y el botón lo dice.

import { useEffect, useRef, useState } from 'react'
import type { Vehiculo } from '../contract'
import type { Frame } from '../lib/turno'
import { Icon } from '../ui/icons'
import { debeCallar, frasesDelTurno, siguienteFrase, type Dicha } from './frases'
import { callar, onFuente, prefetch, say, unlock, type FuenteVoz } from './nuez'

interface Props {
  frames: Frame[]
  t: number
  isPlaying: boolean
  vehiculo: Vehiculo
}

export function VozToggle({ frames, t, isPlaying, vehiculo }: Props) {
  const [encendida, setEncendida] = useState(false)
  const [fuente, setFuente] = useState<FuenteVoz>('elevenlabs')
  const ultima = useRef<Dicha | null>(null)
  const ocupada = useRef(false)
  const turnoVoz = useRef(0)
  const tAnterior = useRef(t)

  useEffect(() => onFuente(setFuente), [])

  // Otro turno o voz apagada: nada de lo encolado sigue siendo cierto. Con la voz encendida,
  // cada turno que se carga calienta su cache (también al cambiar de seed a media sesión).
  useEffect(() => {
    callar()
    ultima.current = null
    ocupada.current = false
    if (encendida) void prefetch(frasesDelTurno(frames, vehiculo))
  }, [frames, vehiculo, encendida])

  useEffect(() => {
    const anterior = tAnterior.current
    tAnterior.current = t
    if (!encendida) return
    if (debeCallar(anterior, t, isPlaying, frames.length - 1)) {
      callar()
      ocupada.current = false
    }
    if (!isPlaying) return
    if (ocupada.current) return // a velocidad alta se omite en vez de amontonar
    const dicha = siguienteFrase(frames[t]?.decisiones ?? [], t, vehiculo, ultima.current)
    if (!dicha) return
    ultima.current = dicha
    ocupada.current = true
    const id = ++turnoVoz.current
    void say(dicha.frase).then(() => {
      // Una frase callada que termina tarde no debe liberar a la que suena ahora.
      if (id === turnoVoz.current) ocupada.current = false
    })
  }, [t, isPlaying, encendida, frames, vehiculo])

  const alternar = () => {
    unlock()
    setEncendida((v) => !v)
  }

  const titulo = !encendida
    ? 'Navie voice off'
    : fuente === 'browser'
      ? 'Navie voice on (ElevenLabs unavailable, using browser voice)'
      : 'Navie voice on (ElevenLabs)'

  return (
    <button
      className={`speed-btn voz-toggle ${encendida ? 'is-active' : ''}`}
      title={titulo}
      aria-label={titulo}
      aria-pressed={encendida}
      onClick={alternar}
    >
      {encendida ? Icon.voice : Icon.voiceOff}
      <span>{encendida && fuente === 'browser' ? 'Voice (local)' : 'Voice'}</span>
    </button>
  )
}
