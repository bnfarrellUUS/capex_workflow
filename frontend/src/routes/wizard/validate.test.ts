import { describe, it, expect } from 'vitest'
import { budgetAmountError } from './validate'
import { blankForm } from './types'
import type { RequestForm } from './types'

const form = (over: Partial<RequestForm> = {}): RequestForm =>
  ({ ...blankForm('div-1', '2026-08-06'), ...over })

describe('budgetAmountError', () => {
  it('is silent when the request is not budgeted', () => {
    expect(budgetAmountError(form({ budgeted: false, budget_amount: '' }))).toBeNull()
  })

  it('ignores a stray amount when the flag is off', () => {
    expect(budgetAmountError(form({ budgeted: false, budget_amount: 'nonsense' }))).toBeNull()
  })

  it('requires an amount when budgeted', () => {
    expect(budgetAmountError(form({ budgeted: true, budget_amount: '' })))
      .toBe('Enter the budgeted amount.')
  })

  it('treats whitespace as blank', () => {
    expect(budgetAmountError(form({ budgeted: true, budget_amount: '   ' })))
      .toBe('Enter the budgeted amount.')
  })

  it('rejects a non-numeric amount', () => {
    expect(budgetAmountError(form({ budgeted: true, budget_amount: 'lots' })))
      .toBe('Enter a valid dollar amount.')
  })

  it('rejects zero and negatives', () => {
    expect(budgetAmountError(form({ budgeted: true, budget_amount: '0' })))
      .toBe('Enter a valid dollar amount.')
    expect(budgetAmountError(form({ budgeted: true, budget_amount: '-500' })))
      .toBe('Enter a valid dollar amount.')
  })

  it('accepts a plain amount', () => {
    expect(budgetAmountError(form({ budgeted: true, budget_amount: '50000' }))).toBeNull()
  })

  it('accepts dollar signs, commas and decimals', () => {
    expect(budgetAmountError(form({ budgeted: true, budget_amount: '$50,000.50' }))).toBeNull()
  })
})
