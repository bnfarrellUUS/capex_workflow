let csrfToken: string | null = null

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function resetCsrf(): void {
  csrfToken = null
}

// CSRF/auth failures that mean the cached token is stale and should be refetched.
function _clearsCsrf(status: number): boolean {
  return status === 400 || status === 401 || status === 403
}

async function ensureCsrf(): Promise<string> {
  if (csrfToken) return csrfToken
  const res = await fetch('/api/auth/csrf', { credentials: 'include' })
  if (!res.ok) throw new ApiError(res.status, 'Could not obtain a CSRF token.')
  const data = await res.json()
  csrfToken = data.csrfToken as string
  return csrfToken
}

export async function api<T = unknown>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = {}
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && method !== 'HEAD') headers['X-CSRFToken'] = await ensureCsrf()

  const res = await fetch(`/api${path}`, {
    method,
    credentials: 'include',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (!res.ok) {
    if (_clearsCsrf(res.status)) csrfToken = null
    let message = res.statusText
    try {
      const data = await res.json()
      if (data && data.error) message = data.error
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export async function apiUpload<T = unknown>(path: string, formData: FormData): Promise<T> {
  const token = await ensureCsrf()
  const res = await fetch(`/api${path}`, {
    method: 'POST', credentials: 'include', headers: { 'X-CSRFToken': token }, body: formData,
  })
  if (!res.ok) {
    if (_clearsCsrf(res.status)) csrfToken = null
    let message = res.statusText
    try {
      const d = await res.json()
      if (d && d.error) message = d.error
    } catch {
      /* non-JSON */
    }
    throw new ApiError(res.status, message)
  }
  return (await res.json()) as T
}
