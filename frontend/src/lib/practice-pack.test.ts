import { describe, expect, it } from 'vitest'

import { etiquetaRestriccion, horaDelPack } from './practice-pack'

describe('horaDelPack', () => {
  it('places a probe at its minute within the 8.5-hour shift', () => {
    expect(horaDelPack('2026-03-14T14:00:00', 487)).toBe('22:07')
  })
})

describe('etiquetaRestriccion', () => {
  it('turns a protocol key into readable copy', () => {
    expect(etiquetaRestriccion('flagged_zone_night')).toBe('flagged zone night')
    expect(etiquetaRestriccion(null)).toBe('No binding constraint')
  })
})
