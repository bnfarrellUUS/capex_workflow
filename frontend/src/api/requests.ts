import { api } from './client'

export interface EquipItem {
  id?: string
  units: number
  condition: string
  type: string
  make: string
  model: string
  cost: string
}

export interface CapexRequestData {
  id: string
  number: string
  status: string
  division_id: string | null
  description: string
  budgeted: boolean
  replacement: boolean
  health_safety: boolean
  revenue_generating: boolean
  environmental: boolean
  competitive_bids: boolean
  lease_recommended: boolean
  justification: string
  effect_on_operations: string
  asset_life: string | null
  irr_after_tax: string | null
  first_year_ebit: string | null
  annual_savings: string | null
  payback_years: string | null
  npv_savings: string | null
  total_cost: string | null
  requestor_id: string
  assignee_id: string | null
  requestor_name: string | null
  assignee_name: string | null
  division_name: string | null
  finance_completed: boolean
  equipment_items: EquipItem[]
  actions: {
    action: string
    level: number | null
    comment: string | null
    created_at: string | null
    actor_name: string | null
  }[]
}

export function createDraft(): Promise<CapexRequestData> {
  return api<CapexRequestData>('/requests', { method: 'POST' })
}
export function getRequest(id: string): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}`)
}
export function updateDraft(id: string, patch: Record<string, unknown>): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}`, { method: 'PATCH', body: patch })
}
export function submitRequest(id: string): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}/submit`, { method: 'POST' })
}
export function approveRequest(id: string, comment?: string): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}/approve`, { method: 'POST', body: { comment } })
}
export function rejectRequest(id: string, comment: string): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}/reject`, { method: 'POST', body: { comment } })
}
export function resubmitRequest(id: string): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}/resubmit`, { method: 'POST' })
}
export function completeFinance(id: string, costs: Record<string, string | null>): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}/finance`, { method: 'POST', body: costs })
}
