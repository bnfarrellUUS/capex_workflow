import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listRequests, type RequestSummary } from '../api/requests'
import { Select } from '../components/ui/Select'
import { BrandCard } from '../components/ui/BrandCard'
import { StatusBadge } from '../components/ui/Badge'

const STATUSES = ['', 'DRAFT', 'PENDING_L1', 'PENDING_L2', 'PENDING_L3', 'APPROVED', 'REJECTED']

export default function RequestsListPage() {
  const [scope, setScope] = useState('mine')
  const [status, setStatus] = useState('')
  const { data: rows = [] } = useQuery({
    queryKey: ['requests', scope, status],
    queryFn: () => listRequests({ scope, status: status || undefined }),
  })

  const filters = (
    <div className="flex flex-wrap items-center gap-3 border-b border-border bg-surface-2 px-7 py-3">
      <div className="inline-flex rounded-md border border-border bg-surface p-0.5">
        {(['mine', 'assigned'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className={`rounded px-3 py-1 text-sm font-medium transition ${
              scope === s ? 'bg-accent text-accent-fg' : 'text-muted hover:text-fg'
            }`}
          >
            {s === 'mine' ? 'My Requests' : 'Assigned to me'}
          </button>
        ))}
      </div>
      <div className="w-48">
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s === '' ? 'All statuses' : s}
            </option>
          ))}
        </Select>
      </div>
    </div>
  )

  return (
    <BrandCard title="Requests" subtitle="Capital expenditure requests" subheader={filters}>
      <RequestsTable rows={rows} />
    </BrandCard>
  )
}

export function RequestsTable({ rows }: { rows: RequestSummary[] }) {
  if (rows.length === 0) return <p className="text-sm text-muted">No requests.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
            <th className="py-2 pr-4 font-semibold">Number</th>
            <th className="py-2 pr-4 font-semibold">Status</th>
            <th className="py-2 pr-4 font-semibold">Division</th>
            <th className="py-2 pr-4 font-semibold">Requestor</th>
            <th className="py-2 pr-4 text-right font-semibold">Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-border last:border-0 hover:bg-surface-2">
              <td className="py-2.5 pr-4">
                <Link className="font-medium text-accent hover:underline" to={`/requests/${r.id}`}>
                  {r.number}
                </Link>
              </td>
              <td className="py-2.5 pr-4">
                <StatusBadge status={r.status} />
              </td>
              <td className="py-2.5 pr-4 text-fg">{r.division_name ?? '—'}</td>
              <td className="py-2.5 pr-4 text-fg">{r.requestor_name}</td>
              <td className="py-2.5 pr-4 text-right font-medium text-fg">
                ${Number(r.total_cost ?? 0).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
