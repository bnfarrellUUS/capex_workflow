import type { RequestForm } from './types'
import { AMOUNT } from './types'

/**
 * A request flagged as Budgeted must carry the budgeted dollar amount. Returns
 * the message to show under the field, or null when there is nothing to fix.
 */
export function budgetAmountError(form: RequestForm): string | null {
  if (!form.budgeted) return null
  const raw = AMOUNT(form.budget_amount)
  if (raw === null) return 'Enter the budgeted amount.'
  const n = Number(raw)
  if (!Number.isFinite(n) || n <= 0) return 'Enter a valid dollar amount.'
  return null
}
