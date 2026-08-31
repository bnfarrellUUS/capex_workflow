import { describe, it, expect } from 'vitest'
import { sortRows } from './tableSort'

interface Row {
  name?: string | null
  count?: number
  active?: boolean
}

const byName = (r: Row) => r.name
const names = (rows: Row[]) => rows.map((r) => r.name)

describe('sortRows', () => {
  it('sorts strings ascending and descending', () => {
    const rows: Row[] = [{ name: 'Corporate' }, { name: 'Airside' }, { name: 'Field' }]
    expect(names(sortRows(rows, byName, 'asc'))).toEqual(['Airside', 'Corporate', 'Field'])
    expect(names(sortRows(rows, byName, 'desc'))).toEqual(['Field', 'Corporate', 'Airside'])
  })

  it('orders numeric strings naturally, not lexically', () => {
    const rows: Row[] = [{ name: '10' }, { name: '2' }, { name: '100' }]
    expect(names(sortRows(rows, byName, 'asc'))).toEqual(['2', '10', '100'])
  })

  it('sorts blanks last regardless of direction', () => {
    const rows: Row[] = [{ name: null }, { name: 'B' }, { name: '' }, { name: 'A' }]
    expect(names(sortRows(rows, byName, 'asc'))).toEqual(['A', 'B', null, ''])
    expect(names(sortRows(rows, byName, 'desc'))).toEqual(['B', 'A', null, ''])
  })

  it('sorts numbers numerically', () => {
    const rows: Row[] = [{ count: 12 }, { count: 3 }, { count: 0 }]
    expect(sortRows(rows, (r) => r.count, 'asc').map((r) => r.count)).toEqual([0, 3, 12])
    expect(sortRows(rows, (r) => r.count, 'desc').map((r) => r.count)).toEqual([12, 3, 0])
  })

  it('sorts booleans with true before false ascending', () => {
    const rows: Row[] = [{ active: false }, { active: true }, { active: false }]
    expect(sortRows(rows, (r) => r.active, 'asc').map((r) => r.active)).toEqual([true, false, false])
    expect(sortRows(rows, (r) => r.active, 'desc').map((r) => r.active)).toEqual([false, false, true])
  })

  it('does not mutate the input array', () => {
    const rows: Row[] = [{ name: 'B' }, { name: 'A' }]
    sortRows(rows, byName, 'asc')
    expect(names(rows)).toEqual(['B', 'A'])
  })
})
