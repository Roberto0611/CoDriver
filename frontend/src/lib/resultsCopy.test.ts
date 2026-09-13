// El panel de distribución no puede decir un número distinto al de la tabla que
// genera scripts/results_table.py. Si alguien regenera la tabla (otro motor, otro
// n) y no actualiza resultsCopy.ts, esto truena antes de que llegue al pitch.

import { describe, it, expect } from 'vitest'

import tabla from '../../../results_table.csv?raw'
import { RIVALES, SEEDS_TUNEO, porcentajeDelOracle } from './resultsCopy'

const lineas = tabla.split(/\r?\n/).filter(Boolean)

function comentario(prefijo: string): string {
  const linea = lineas.find((l) => l.startsWith(`# ${prefijo}`))
  if (!linea) throw new Error(`results_table.csv sin la línea "${prefijo}"`)
  return linea
}

function mediasDeLaTabla(): Record<string, number> {
  const datos = lineas.filter((l) => !l.startsWith('#'))
  const columnas = datos[0].split(',')
  const politica = columnas.indexOf('policy')
  const media = columnas.indexOf('mean_earnings_mxn')
  return Object.fromEntries(
    datos.slice(1).map((fila) => {
      const celdas = fila.split(',')
      return [celdas[politica], Number(celdas[media])]
    })
  )
}

describe('RIVALES espeja results_table.csv', () => {
  it('las seis medias son las de la tabla, sin redondeo a mano', () => {
    expect(RIVALES.media).toEqual(mediasDeLaTabla())
  })

  it('n y el rango de REPORTE son los del encabezado', () => {
    const [desde, hasta] = RIVALES.seedsReporte
    expect(comentario('Reporting seeds')).toContain(
      `${desde}-${hasta}, n=${RIVALES.turnos} held-out shifts`
    )
    expect(hasta - desde + 1).toBe(RIVALES.turnos)
  })

  it('la config del pie de la rejilla es la del encabezado', () => {
    const { duracionMin, vehiculo, horaInicio } = RIVALES.config
    const linea = comentario('Config')
    expect(linea).toContain(`vehicle ${vehiculo}, start ${String(horaInicio).padStart(2, '0')}:00`)
    expect(linea).toContain(`${duracionMin}-min shift`)
  })

  it('el rango de TUNEO es el del encabezado', () => {
    expect(comentario('Tuning seeds')).toContain(`${SEEDS_TUNEO[0]}-${SEEDS_TUNEO[1]}`)
  })
})

describe('porcentajeDelOracle', () => {
  it('OurAgent sobre Oracle, a un decimal', () => {
    const esperado = Math.round((RIVALES.media.OurAgent / RIVALES.media.Oracle) * 1000) / 10
    expect(porcentajeDelOracle()).toBe(esperado)
  })
})
