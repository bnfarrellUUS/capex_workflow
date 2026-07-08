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

async function ensureCsrf(): Promise<string> {
  if (csrfToken) return csrfToken
  const res = await fetch('/api/auth/csrf', { credentials: 'include' })
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
    if (res.status === 401) csrfToken = null
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
