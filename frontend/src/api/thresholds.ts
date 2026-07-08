import { api } from './client'

export interface Threshold {
  level: number
  max_amount: string | null
  approver_id: string | null
}

export function listThresholds(): Promise<Threshold[]> {
  return api<Threshold[]>('/thresholds')
}
export function putThresholds(thresholds: Threshold[]): Promise<Threshold[]> {
  return api<Threshold[]>('/thresholds', { method: 'PUT', body: { thresholds } })
}
