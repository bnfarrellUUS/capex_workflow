import { api } from './client'

export interface Division {
  id: string
  number: string
  name: string
  active: boolean
  l1_approver_ids: string[]
  l1_approver_names?: string[]
}

export interface DivisionInput {
  number: string
  name: string
  active?: boolean
  l1_approver_ids?: string[]
}

export function listDivisions(): Promise<Division[]> {
  return api<Division[]>('/divisions')
}
export function createDivision(body: DivisionInput): Promise<Division> {
  return api<Division>('/divisions', { method: 'POST', body })
}
export function updateDivision(id: string, body: DivisionInput): Promise<Division> {
  return api<Division>(`/divisions/${id}`, { method: 'PATCH', body })
}
