import { describe, expect, it } from 'vitest'
import { sayUrl } from './nuez'

describe('sayUrl', () => {
  it('points at the backend voice route and encodes the text', () => {
    expect(sayUrl("Skip it. That's 22 minutes & 26 back.", 'http://api')).toBe(
      "http://api/api/voice/say?text=Skip%20it.%20That's%2022%20minutes%20%26%2026%20back."
    )
  })

  it('trims surrounding whitespace so the backend cache key matches', () => {
    expect(sayUrl('  Skip it. ', 'http://api')).toBe('http://api/api/voice/say?text=Skip%20it.')
  })
})
