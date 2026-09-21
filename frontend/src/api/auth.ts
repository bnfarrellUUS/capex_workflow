import { api, resetCsrf } from './client'

export interface CurrentUser {
  id: string
  name: string
  email: string
  roles: string[]
  division_id: string | null
  must_change_password: boolean
  /** How this session signed in. SSO users have no password to change. */
  auth_method: 'sso' | 'password'
}

export interface AuthConfig {
  ok: boolean
  sso_enabled: boolean
}

/** Unauthenticated: tells the login screen whether to offer SSO. */
export function getAuthConfig(): Promise<AuthConfig> {
  return api<AuthConfig>('/auth/config')
}

export function fetchMe(): Promise<CurrentUser> {
  return api<CurrentUser>('/auth/me')
}

export function login(email: string, password: string): Promise<CurrentUser> {
  return api<CurrentUser>('/auth/login', { method: 'POST', body: { email, password } })
}

export async function logout(): Promise<void> {
  await api('/auth/logout', { method: 'POST' })
  resetCsrf()
}

export function setPassword(new_password: string): Promise<CurrentUser> {
  return api<CurrentUser>('/auth/set-password', { method: 'POST', body: { new_password } })
}
