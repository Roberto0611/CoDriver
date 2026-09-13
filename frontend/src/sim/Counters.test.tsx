// El resumen final: la hora de regreso sale del config, no de un texto fijo.

import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'

import type { TurnoMeta } from '../lib/turno'
import { Counters } from './Counters'

const texto = (html: string) =>
  html
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const meta = (politica: TurnoMeta['politica']): TurnoMeta => ({
  politica,
  seed: 2000,
  ganado: 250,
  entregas: 5,
  rechazos: 3,
  ofertas_totales: 8,
  violaciones: 0,
  llego_tarde: false,
  regreso_en: 104.2,
  cancelados: 0,
})

const base = {
  greedy: { ganado: 90, entregas: 1, saltadas: 2 },
  nuez: { ganado: 120, entregas: 3, saltadas: 1 },
  greedyMeta: meta('greedy'),
  nuezMeta: meta('nuez'),
  terminado: true,
}

describe('Counters', () => {
  it('pluraliza las entregas', () => {
    const t = texto(renderToStaticMarkup(<Counters {...base} />))
    expect(t).toContain('1 delivery · 2 skipped')
    expect(t).toContain('3 deliveries · 1 skipped')
    expect(t).not.toContain('1 deliveries')
  })

  it('con config, la hora límite es inicio + duración − margen', () => {
    const t = texto(
      renderToStaticMarkup(
        <Counters {...base} config={{ hora_inicio: 14, duracion_min: 120, margen_min: 10 }} />
      )
    )
    expect(t).toContain('Back by 15:50')
    expect(t).not.toContain('14:50')
  })

  it('otro turno, otra hora', () => {
    const t = texto(
      renderToStaticMarkup(
        <Counters {...base} config={{ hora_inicio: 16, duracion_min: 480, margen_min: 10 }} />
      )
    )
    expect(t).toContain('Back by 23:50')
  })

  it('con regresar_al_ancla explícito sigue siendo "Back by"', () => {
    const t = texto(
      renderToStaticMarkup(
        <Counters
          {...base}
          config={{ hora_inicio: 14, duracion_min: 120, margen_min: 10, regresar_al_ancla: true }}
        />
      )
    )
    expect(t).toContain('Back by 15:50')
    expect(t).toContain('104.2 min')
  })

  it('sin regreso al ancla no promete un regreso', () => {
    const t = texto(
      renderToStaticMarkup(
        <Counters
          {...base}
          config={{ hora_inicio: 14, duracion_min: 120, margen_min: 10, regresar_al_ancla: false }}
        />
      )
    )
    expect(t).toContain('Deliveries done by 15:50')
    expect(t).not.toContain('Back by')
    expect(t).not.toContain('104.2 min')
  })

  it('sin config no inventa una hora', () => {
    const t = texto(renderToStaticMarkup(<Counters {...base} />))
    expect(t).not.toMatch(/Back by \d/)
    expect(t).toContain('Back at anchor')
    expect(t).toContain('104.2 min')
  })
})
