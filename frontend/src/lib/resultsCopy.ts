// Los números del panel de distribución, cada uno con su fuente. Nada aquí se
// escribe a ojo: si el motor cambia, se regeneran con los comandos de abajo y
// resultsCopy.test.ts compara RIVALES contra results_table.csv.

/** seeds.py: TUNEO es donde se construyó la tabla de valor y se barrieron parámetros. */
export const SEEDS_TUNEO: readonly [number, number] = [0, 1999]

/**
 * `python scripts/results_table.py` → results_table.csv: 50 turnos de REPORTE,
 * 120 min, moto (20 kg, 20 L), 14:00, ancla Tec, margen 10, con regreso al ancla.
 * Medias de `mean_earnings_mxn`.
 */
export const RIVALES = {
  turnos: 50,
  seedsReporte: [2000, 2049] as readonly [number, number],
  config: { duracionMin: 120, vehiculo: 'moto', horaInicio: 14 },
  media: {
    AcceptAll: 153.73,
    HighestPay: 69.58,
    NearestFirst: 110.9,
    GreedyRate: 140.34,
    OurAgent: 246.31,
    Oracle: 258.89,
  },
} as const

/**
 * `python comparar.py 200` y `python comparar.py 200 --shocks`: Nuez contra
 * greedy en 200 turnos de REPORTE, misma config. No hay CSV de esto; si cambia
 * el motor hay que volver a correrlos y copiar el DELTA y el "ganó en".
 */
export const DELTA_200 = {
  turnos: 200,
  seedsReporte: [2000, 2199] as readonly [number, number],
  normal: { deltaPct: 81.6, gana: 175 },
  shocks: { deltaPct: 83.8, gana: 172 },
} as const

/**
 * Lo que dice `public/distribucion_ganancias.png` (título y leyenda de la imagen),
 * no el motor de hoy: la imagen es de un build anterior y ningún script del repo
 * la regenera. Si se regenera la imagen, se actualiza esto; si no, el pie la
 * describe tal cual es.
 */
export const HISTOGRAMA = {
  turnos: 200,
  media: { greedy: 200, navie: 259 },
} as const

/**
 * Qué fracción del Oracle captura Navie (OurAgent). El Oracle (`oracle.resolver`) se queda con
 * lo mejor entre su búsqueda en haz y las cinco políticas online, OurAgent
 * incluida: es el mejor plan offline que conocemos, no una cota demostrada.
 */
export function porcentajeDelOracle(): number {
  return Math.round((RIVALES.media.OurAgent / RIVALES.media.Oracle) * 1000) / 10
}
