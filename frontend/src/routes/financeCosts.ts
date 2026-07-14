import type { CapexRequestData } from '../api/requests'

export type CostField = 'cost_autos_trucks' | 'cost_machinery' | 'cost_improvements'
  | 'cost_furniture' | 'cost_permits' | 'cost_misc'

export const FINANCE_FIELDS: [CostField, string][] = [
  ['cost_autos_trucks', 'Autos & Trucks'], ['cost_machinery', 'Machinery & Equipment'],
  ['cost_improvements', 'Improvements'], ['cost_furniture', 'Furniture & Fixtures'],
  ['cost_permits', 'Permits'], ['cost_misc', 'Misc'],
]

/** Parse the finance form values into an API payload. Accepts plain numbers
 * with optional `$` and thousands separators; blank fields become null.
 * Returns the labels of any fields that are not dollar amounts. */
export function parseFinanceCosts(vals: Record<string, string>): {
  costs: Record<string, string | null>
  invalid: string[]
} {
  const costs: Record<string, string | null> = {}
  const invalid: string[] = []
  for (const [key, label] of FINANCE_FIELDS) {
    const raw = (vals[key] ?? '').trim().replace(/[$,]/g, '')
    if (!raw) {
      costs[key] = null
    } else if (Number.isFinite(Number(raw)) && Number(raw) >= 0) {
      costs[key] = raw
    } else {
      invalid.push(label)
    }
  }
  return { costs, invalid }
}

export function financeFormValues(req: CapexRequestData): Record<string, string> {
  return Object.fromEntries(FINANCE_FIELDS.map(([key]) => [key, req[key] ?? '']))
}

/** Sum the valid dollar amounts in the form values, in cents (invalid or
 * blank fields count as 0). Cents avoid float drift when comparing totals. */
export function financeTotalCents(vals: Record<string, string>): number {
  const { costs } = parseFinanceCosts(vals)
  return Object.values(costs).reduce(
    (sum, v) => sum + (v ? Math.round(Number(v) * 100) : 0), 0)
}

export function dollars(cents: number): string {
  return (cents / 100).toLocaleString(undefined, { maximumFractionDigits: 2 })
}
