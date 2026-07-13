import type { RequestSummary } from '../api/requests'

export type SortKey = 'number' | 'status' | 'division_name' | 'requestor_name' | 'total_cost'
export type SortDir = 'asc' | 'desc'

// Workflow order, not alphabetical.
const STATUS_ORDER = ['DRAFT', 'PENDING_L1', 'PENDING_L2', 'PENDING_L3', 'APPROVED', 'REJECTED']

export function filterRequests(rows: RequestSummary[], query: string): RequestSummary[] {
  const q = query.trim().toLowerCase()
  if (!q) return rows
  return rows.filter((r) =>
    [r.number, r.division_name, r.requestor_name].some((f) => f?.toLowerCase().includes(q)),
  )
}

export function sortRequests(rows: RequestSummary[], key: SortKey, dir: SortDir): RequestSummary[] {
  const sign = dir === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    if (key === 'total_cost') {
      return sign * (Number(a.total_cost ?? 0) - Number(b.total_cost ?? 0))
    }
    if (key === 'status') {
      return sign * (STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status))
    }
    const av = a[key]
    const bv = b[key]
    // Blanks sort last regardless of direction.
    if (!av && !bv) return 0
    if (!av) return 1
    if (!bv) return -1
    return sign * av.localeCompare(bv)
  })
}
