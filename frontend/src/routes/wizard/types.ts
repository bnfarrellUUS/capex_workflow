import type { CapexRequestData, EquipItem } from '../../api/requests'

export interface RequestForm {
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
  asset_life: string
  irr_after_tax: string
  first_year_ebit: string
  annual_savings: string
  payback_years: string
  npv_savings: string
  division_id: string
  equipment_items: EquipItem[]
}

export function toForm(r: CapexRequestData): RequestForm {
  return {
    description: r.description ?? '',
    budgeted: r.budgeted, replacement: r.replacement, health_safety: r.health_safety,
    revenue_generating: r.revenue_generating, environmental: r.environmental,
    competitive_bids: r.competitive_bids, lease_recommended: r.lease_recommended,
    justification: r.justification ?? '',
    effect_on_operations: r.effect_on_operations ?? '',
    asset_life: r.asset_life ?? '',
    irr_after_tax: r.irr_after_tax ?? '',
    first_year_ebit: r.first_year_ebit ?? '',
    annual_savings: r.annual_savings ?? '',
    payback_years: r.payback_years ?? '',
    npv_savings: r.npv_savings ?? '',
    division_id: r.division_id ?? '',
    equipment_items: r.equipment_items.map((i) => ({ ...i })),
  }
}

const DEC = (s: string) => (s.trim() === '' ? null : s)

export function toPayload(f: RequestForm): Record<string, unknown> {
  return {
    description: f.description,
    budgeted: f.budgeted, replacement: f.replacement, health_safety: f.health_safety,
    revenue_generating: f.revenue_generating, environmental: f.environmental,
    competitive_bids: f.competitive_bids, lease_recommended: f.lease_recommended,
    justification: f.justification,
    effect_on_operations: f.effect_on_operations,
    asset_life: f.asset_life || null,
    irr_after_tax: DEC(f.irr_after_tax),
    first_year_ebit: DEC(f.first_year_ebit),
    annual_savings: DEC(f.annual_savings),
    payback_years: DEC(f.payback_years),
    npv_savings: DEC(f.npv_savings),
    division_id: f.division_id || null,
    equipment_items: f.equipment_items.map((i) => ({
      units: Number(i.units) || 0, condition: i.condition, type: i.type,
      make: i.make, model: i.model, cost: i.cost.trim() === '' ? '0' : i.cost,
    })),
  }
}

export function equipmentTotal(items: EquipItem[]): number {
  return items.reduce((sum, i) => sum + (Number(i.cost) || 0), 0)
}
