import { api, resetCsrf } from './client'

export interface CurrentUser {
  id: string
  name: string
  email: string
  roles: string[]
  division_id: string | null
  must_change_password: boolean
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
