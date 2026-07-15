import { describe, it, expect, beforeEach, vi } from 'vitest'
import { api, resetCsrf } from './client'

function fakeResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'x',
    json: async () => body,
  } as Response
}

beforeEach(() => {
  resetCsrf()
  vi.unstubAllGlobals()
})

describe('api client', () => {
  it('GET includes credentials and no CSRF header', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(fakeResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)
    const data = await api<{ ok: boolean }>('/auth/me')
    expect(data).toEqual({ ok: true })
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/auth/me')
    expect(opts.credentials).toBe('include')
    expect(opts.headers['X-CSRFToken']).toBeUndefined()
  })

  it('POST fetches CSRF token then attaches X-CSRFToken', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(fakeResponse(200, { csrfToken: 'tok123' }))
      .mockResolvedValueOnce(fakeResponse(200, { id: '1' }))
    vi.stubGlobal('fetch', fetchMock)
    await api('/auth/login', { method: 'POST', body: { email: 'a' } })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/csrf')
    const loginOpts = fetchMock.mock.calls[1][1]
    expect(loginOpts.headers['X-CSRFToken']).toBe('tok123')
    expect(loginOpts.headers['Content-Type']).toBe('application/json')
    expect(loginOpts.body).toBe(JSON.stringify({ email: 'a' }))
  })

  it('throws ApiError with server error message on non-ok', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(fakeResponse(401, { error: 'nope' }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(api('/auth/me')).rejects.toMatchObject({ status: 401, message: 'nope' })
  })
})
