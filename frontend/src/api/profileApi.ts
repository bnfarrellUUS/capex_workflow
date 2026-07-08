import { api } from './client'

export interface Profile {
  id: string
  username: string
  name: string
  email: string
  roles: string[]
  division_id: string | null
  delegate_id: string | null
}

export interface DelegateOption {
  id: string
  name: string
}

export function getProfile(): Promise<Profile> {
  return api<Profile>('/profile')
}
export function setDelegate(delegate_id: string | null): Promise<Profile> {
  return api<Profile>('/profile', { method: 'PATCH', body: { delegate_id } })
}
export function changePassword(current_password: string, new_password: string): Promise<void> {
  return api('/profile/password', { method: 'POST', body: { current_password, new_password } })
}
export function listDelegateOptions(): Promise<DelegateOption[]> {
  return api<DelegateOption[]>('/profile/delegate-options')
}
