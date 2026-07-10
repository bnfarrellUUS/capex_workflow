// Preserve the page the user was trying to reach (e.g. an email deep link to
// /requests/42) across the login round-trip via a ?next= query param.

/** Build the /login URL carrying the current location as ?next=. */
export function loginPathWithNext(pathname: string, search: string): string {
  const target = pathname + search
  if (pathname === '/login' || target === '/') return '/login'
  return `/login?next=${encodeURIComponent(target)}`
}

/** Validate a ?next= value: only same-app absolute paths, else the dashboard. */
export function safeNext(raw: string | null): string {
  if (raw && raw.startsWith('/') && !raw.startsWith('//')) return raw
  return '/'
}
