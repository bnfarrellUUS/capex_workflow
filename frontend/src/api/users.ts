import { api } from './client'

export interface AdminUser {
  id: string
  email: string
  name: string
  roles: string[]
  active: boolean
  division_id: string | null
}

export interface UserInput {
  email: string
  name: string
  roles: string[]
  division_id: string | null
  active?: boolean
}

export function listUsers(): Promise<AdminUser[]> {
  return api<AdminUser[]>('/users')
}
export function createUser(body: UserInput): Promise<AdminUser> {
  return api<AdminUser>('/users', { method: 'POST', body })
}
export function updateUser(id: string, body: UserInput): Promise<AdminUser> {
  return api<AdminUser>(`/users/${id}`, { method: 'PATCH', body })
}
export function resetUserPassword(id: string): Promise<void> {
  return api(`/users/${id}/reset-password`, { method: 'POST' })
}
export function deleteUser(id: string): Promise<void> {
  return api(`/users/${id}`, { method: 'DELETE' })
}
