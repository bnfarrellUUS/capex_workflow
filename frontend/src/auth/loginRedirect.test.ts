import { describe, it, expect } from 'vitest'
import { loginPathWithNext, safeNext } from './loginRedirect'

describe('loginPathWithNext', () => {
  it('carries the current path and query as ?next=', () => {
    expect(loginPathWithNext('/requests/42', '')).toBe('/login?next=%2Frequests%2F42')
    expect(loginPathWithNext('/requests', '?status=PENDING_L1')).toBe(
      '/login?next=%2Frequests%3Fstatus%3DPENDING_L1',
    )
  })

  it('omits next for the dashboard and the login page itself', () => {
    expect(loginPathWithNext('/', '')).toBe('/login')
    expect(loginPathWithNext('/login', '?next=%2Fx')).toBe('/login')
  })
})

describe('safeNext', () => {
  it('accepts in-app absolute paths', () => {
    expect(safeNext('/requests/42')).toBe('/requests/42')
  })

  it('falls back to the dashboard for missing or external values', () => {
    expect(safeNext(null)).toBe('/')
    expect(safeNext('https://evil.example')).toBe('/')
    expect(safeNext('//evil.example')).toBe('/')
  })
})
