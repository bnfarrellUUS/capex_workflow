import { api } from './client'

export interface Region {
  id: string
  name: string
  active: boolean
  vp_approver_ids: string[]
  vp_approver_names?: string[]
  division_count?: number
}

export interface RegionInput {
  name: string
  active?: boolean
  vp_approver_ids?: string[]
}

export function listRegions(): Promise<Region[]> {
  return api<Region[]>('/regions')
}
export function createRegion(body: RegionInput): Promise<Region> {
  return api<Region>('/regions', { method: 'POST', body })
}
export function updateRegion(id: string, body: RegionInput): Promise<Region> {
  return api<Region>(`/regions/${id}`, { method: 'PATCH', body })
}
