import { describe, it, expect, vi } from 'vitest'
import { exportRequestsPath, addComment } from './requests'

vi.mock('./client', () => ({
  api: vi.fn(),
  apiUpload: vi.fn(),
  ApiError: class ApiError extends Error {},
}))
import { api } from './client'

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

describe('addComment', () => {
  it('posts a comment body to the comments endpoint', async () => {
    vi.mocked(api).mockResolvedValue({} as never)
    await addComment('req-1', 'Where are the bids?')
    expect(api).toHaveBeenCalledWith('/requests/req-1/comments', {
      method: 'POST', body: { body: 'Where are the bids?' },
    })
  })
})
