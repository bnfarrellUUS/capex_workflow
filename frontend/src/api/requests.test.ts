import { describe, it, expect } from 'vitest'
import { exportRequestsPath } from './requests'

describe('exportRequestsPath', () => {
  it('returns the bare path with no params', () => {
    expect(exportRequestsPath()).toBe('/api/requests/export.xlsx')
    expect(exportRequestsPath({ scope: '', status: '', q: '' })).toBe(
      '/api/requests/export.xlsx')
  })

  it('includes scope, status and trimmed q', () => {
    expect(exportRequestsPath({ scope: 'all', status: 'APPROVED', q: ' CX01 ' }))
      .toBe('/api/requests/export.xlsx?scope=all&status=APPROVED&q=CX01')
  })

  it('drops blank q and encodes special characters', () => {
    expect(exportRequestsPath({ scope: 'mine', q: '   ' })).toBe(
      '/api/requests/export.xlsx?scope=mine')
    expect(exportRequestsPath({ q: 'a&b' })).toBe(
      '/api/requests/export.xlsx?q=a%26b')
  })
})
