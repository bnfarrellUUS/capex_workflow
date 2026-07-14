import { describe, it, expect } from 'vitest'
import { parseFinanceCosts } from './financeCosts'

describe('parseFinanceCosts', () => {
  it('passes through plain numbers and nulls blanks', () => {
    const { costs, invalid } = parseFinanceCosts({
      cost_autos_trucks: '45600', cost_permits: '  ',
    })
    expect(invalid).toEqual([])
    expect(costs.cost_autos_trucks).toBe('45600')
    expect(costs.cost_permits).toBeNull()
    expect(costs.cost_misc).toBeNull()
  })

  it('strips $ signs and thousands separators', () => {
    const { costs, invalid } = parseFinanceCosts({
      cost_machinery: '$30,000.50',
    })
    expect(invalid).toEqual([])
    expect(costs.cost_machinery).toBe('30000.50')
  })

  it('reports the labels of non-numeric fields', () => {
    const { invalid } = parseFinanceCosts({
      cost_autos_trucks: 'Truck', cost_misc: 'F-150', cost_permits: '250',
    })
    expect(invalid).toEqual(['Autos & Trucks', 'Misc'])
  })

  it('rejects negative amounts', () => {
    const { invalid } = parseFinanceCosts({ cost_improvements: '-5' })
    expect(invalid).toEqual(['Improvements'])
  })
})
