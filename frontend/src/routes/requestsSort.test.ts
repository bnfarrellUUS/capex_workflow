import { describe, it, expect } from 'vitest'
import { sortRequests } from './requestsSort'
import type { RequestSummary } from '../api/requests'

function row(over: Partial<RequestSummary>): RequestSummary {
  return {
    id: 'x', number: 'CX000001', status: 'DRAFT', total_cost: null,
    division_name: null, requestor_name: null, assignee_name: null, created_at: null,
    ...over,
  }
}

describe('sortRequests', () => {
  it('sorts total_cost numerically, treating null as 0', () => {
    const rows = [row({ id: 'a', total_cost: '1000.00' }), row({ id: 'b', total_cost: null }), row({ id: 'c', total_cost: '250.50' })]
    expect(sortRequests(rows, 'total_cost', 'asc').map(r => r.id)).toEqual(['b', 'c', 'a'])
    expect(sortRequests(rows, 'total_cost', 'desc').map(r => r.id)).toEqual(['a', 'c', 'b'])
  })

  it('sorts status in workflow order, not alphabetically', () => {
    const rows = [row({ id: 'a', status: 'APPROVED' }), row({ id: 'b', status: 'DRAFT' }), row({ id: 'c', status: 'PENDING_L2' })]
    expect(sortRequests(rows, 'status', 'asc').map(r => r.id)).toEqual(['b', 'c', 'a'])
  })

  it('sorts text columns alphabetically with blanks last in both directions', () => {
    const rows = [row({ id: 'a', division_name: 'West' }), row({ id: 'b', division_name: null }), row({ id: 'c', division_name: 'East' })]
    expect(sortRequests(rows, 'division_name', 'asc').map(r => r.id)).toEqual(['c', 'a', 'b'])
    expect(sortRequests(rows, 'division_name', 'desc').map(r => r.id)).toEqual(['a', 'c', 'b'])
  })

  it('does not mutate the input array', () => {
    const rows = [row({ id: 'a', number: 'CX000002' }), row({ id: 'b', number: 'CX000001' })]
    sortRequests(rows, 'number', 'asc')
    expect(rows.map(r => r.id)).toEqual(['a', 'b'])
  })
})
