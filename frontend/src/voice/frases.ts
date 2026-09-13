// Qué dice Nuez en voz alta mientras se reproduce un turno grabado.
//
// Frases cortas en inglés, armadas desde `accion`, `restriccion` y `terminos`, no desde
// la `razon` (viene en español y cambia en cada decisión). Pocas frases distintas =
// pocos caracteres de ElevenLabs y todo cabe en la cache de disco para el demo sin red.
// Los saltos por dinero no se dicen: pasan casi cada minuto y taparían lo importante.

import type { Decision, Restriccion, Vehiculo } from '../contract'
import type { Frame } from '../lib/turno'

/** Minutos simulados antes de repetir la misma frase seguida. */
export const SILENCIO_REPETIDA_MIN = 15

import { getVoiceLanguage } from './nuez'

const VEHICULO_HABLADO: Record<string, Record<Vehiculo, string>> = {
  en: { moto: 'motorbike', car: 'car', bike: 'bike' },
  es: { moto: 'moto', car: 'auto', bike: 'bicicleta' },
  hi: { moto: 'motorcycle', car: 'gadi', bike: 'cycle' },
}

const DURAS: Record<string, Record<Exclude<Restriccion, 'reservation_wage'>, (v: Vehiculo) => string>> = {
  en: {
    flagged_zone_night: () => "Skip. I won't send you into a flagged zone after 10 PM.",
    mandatory_break: () => 'Skip. Four hours riding. Take your 20 minute break.',
    heat_rule: () => 'Skip. Heat rule. 90 minutes riding in this heat is the limit.',
    shift_end_infeasible: () => "Skip. You couldn't finish it before your shift ends.",
    vehicle_capacity: (v) => `Skip. That order won't fit on your ${VEHICULO_HABLADO.en[v]}.`,
  },
  es: {
    flagged_zone_night: () => "Rechazar. No te enviaré a una zona de riesgo después de las 10 PM.",
    mandatory_break: () => 'Rechazar. Cuatro horas manejando. Toma tu descanso de 20 minutos.',
    heat_rule: () => 'Rechazar. Regla de calor. 90 minutos manejando en este calor es el límite.',
    shift_end_infeasible: () => "Rechazar. No podrías terminarlo antes de que acabe tu turno.",
    vehicle_capacity: (v) => `Rechazar. Ese pedido no cabe en tu ${VEHICULO_HABLADO.es[v]}.`,
  },
  hi: {
    flagged_zone_night: () => "Chhod do. Raat das baje ke baad main tumhe khatre wale ilake mein nahi bhejungi.",
    mandatory_break: () => 'Chhod do. Chaar ghante ho gaye. Apna 20 minute ka break lo.',
    heat_rule: () => 'Chhod do. Garmi ki wajah se. Is garmi mein nabbe minute ki limit hai.',
    shift_end_infeasible: () => "Chhod do. Tum ise apni shift khatam hone se pehle poora nahi kar paoge.",
    vehicle_capacity: (v) => `Chhod do. Woh order tumhari ${VEHICULO_HABLADO.hi[v]} par fit nahi aayega.`,
  }
}

export function fraseVoz(d: Decision, vehiculo: Vehiculo): string | null {
  const { elLang } = getVoiceLanguage()
  const lang = DURAS[elLang] ? elLang : 'en'

  if (d.accion === 'aceptar') {
    const pago = Math.round(d.terminos.pago_neto ?? 0)
    const mins = Math.round(d.terminos.minutos ?? 0)
    if (lang === 'es') return `Tómalo. ${pago} pesos por ${mins} minutos.`
    if (lang === 'hi') return `Ise le lo. ${mins} minute ke liye ${pago} pesos.`
    return `Take it. ${pago} pesos for ${mins} minutes.`
  }
  if (!d.restriccion || d.restriccion === 'reservation_wage') return null
  return DURAS[lang][d.restriccion](vehiculo)
}

/**
 * La narración live también dice la reacción a un shock por dinero. El motor conserva
 * su `razon` en español para auditoría, así que la voz nunca la debe leer directamente:
 * esta variante arma una explicación breve y siempre inglesa desde datos deterministas.
 */
export function fraseVozEnVivo(d: Decision, vehiculo: Vehiculo): string {
  const frase = fraseVoz(d, vehiculo)
  if (frase) return frase
  const { elLang } = getVoiceLanguage()
  const lang = DURAS[elLang] ? elLang : 'en'
  const pago = Math.round(d.terminos.pago_neto ?? 0)
  const mins = Math.round(d.terminos.minutos ?? 0)
  
  if (lang === 'es') return `Rechazar. ${pago} pesos por ${mins} minutos está por debajo de lo esperado.`
  if (lang === 'hi') return `Chhod do. ${mins} minute ke liye ${pago} pesos ummeed se kam hai.`
  return `Skip. ${pago} pesos for ${mins} minutes is below the expected return.`
}

export interface Dicha {
  frase: string
  t: number
}

/**
 * Qué decir en el minuto `t`, dado lo último que se dijo. Aceptar gana sobre rechazar;
 * la misma frase no se repite hasta que pasen SILENCIO_REPETIDA_MIN minutos.
 */
export function siguienteFrase(
  decisiones: Decision[],
  t: number,
  vehiculo: Vehiculo,
  ultima: Dicha | null
): Dicha | null {
  const ordenadas = [...decisiones].sort(
    (a, b) => Number(b.accion === 'aceptar') - Number(a.accion === 'aceptar')
  )
  for (const d of ordenadas) {
    const frase = fraseVoz(d, vehiculo)
    if (!frase) continue
    const repetida = ultima?.frase === frase && t - ultima.t < SILENCIO_REPETIDA_MIN
    if (!repetida) return { frase, t }
  }
  return null
}

/**
 * ¿Cortar la frase que suena? Sí ante un seek a mano o una pausa: habla de otro minuto.
 * No cuando el reproductor se detiene solo en el último minuto (SimView pausa al llegar al
 * final): ahí se amontonan los rechazos de fin de turno y cortarlos arruina el cierre.
 */
export function debeCallar(
  tAnterior: number,
  t: number,
  isPlaying: boolean,
  ultimoMinuto: number
): boolean {
  const salto = t !== tAnterior && t !== tAnterior + 1
  if (salto) return true
  return !isPlaying && t !== ultimoMinuto
}

/** Las frases distintas que sonarían en el turno completo. Sirve para calentar la cache. */
export function frasesDelTurno(frames: Frame[], vehiculo: Vehiculo): string[] {
  const vistas = new Set<string>()
  let ultima: Dicha | null = null
  for (const f of frames) {
    const dicha = siguienteFrase(f.decisiones, f.t, vehiculo, ultima)
    if (!dicha) continue
    ultima = dicha
    vistas.add(dicha.frase)
  }
  return [...vistas]
}
