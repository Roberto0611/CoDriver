// Lo que el juez lee en el panel: cuántos turnos, qué seeds, y qué es el Oracle.

import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'

import { porcentajeDelOracle } from '../lib/resultsCopy'
import { Distribution } from './Distribution'

const texto = (html: string) =>
  html
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

describe('Distribution', () => {
  const abierto = texto(renderToStaticMarkup(<Distribution abierto />))

  it('no vende al Oracle como óptimo teórico', () => {
    expect(abierto).not.toMatch(/theoretical optimum/i)
    expect(abierto).not.toMatch(/theoretical/i)
    expect(abierto).toContain('best-known offline plan')
    expect(abierto).toContain('not a proven optimum')
  })

  it('el porcentaje del Oracle sale de la tabla de 50 turnos', () => {
    // 265.21 / 280.57 hoy; resultsCopy.test.ts ata RIVALES a results_table.csv.
    expect(abierto).toContain(`Navie reaches ${porcentajeDelOracle()}% of it`)
  })

  it('cada bloque de números dice de cuántos turnos sale', () => {
    // El titular (+33.5%) es de comparar.py 200; la rejilla es results_table.csv (50).
    expect(abierto).toContain('Over 200 held-out shifts')
    expect(abierto).toContain('Mean earnings, 50 held-out shifts')
    expect(abierto).toContain('· 120 min, moto, 14:00')
  })

  it('nombra los dos conjuntos de seeds', () => {
    expect(abierto).toContain('TUNEO 0–1999')
    expect(abierto).toContain('REPORTE 2000–2199')
    expect(abierto).toContain('2000–2049')
  })

  it('cerrado no afirma un n que no enseña', () => {
    const cerrado = texto(renderToStaticMarkup(<Distribution />))
    expect(cerrado).not.toContain('200 shifts')
  })
})
