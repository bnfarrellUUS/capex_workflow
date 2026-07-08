import { api, resetCsrf } from './client'

export interface CurrentUser {
  id: string
  username: string
  name: string
  email: string
  roles: string[]
}

export function fetchMe(): Promise<CurrentUser> {
  return api<CurrentUser>('/auth/me')
}

export function login(username: string, password: string): Promise<CurrentUser> {
  return api<CurrentUser>('/auth/login', { method: 'POST', body: { username, password } })
}

export async function logout(): Promise<void> {
  await api('/auth/logout', { method: 'POST' })
  resetCsrf()
}
