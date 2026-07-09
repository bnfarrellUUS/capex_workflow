import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listRequests, type RequestSummary } from '../api/requests'
import { Select } from '../components/ui/Select'

const STATUSES = ['', 'DRAFT', 'PENDING_L1', 'PENDING_L2', 'PENDING_L3', 'APPROVED', 'REJECTED']

export default function RequestsListPage() {
  const [scope, setScope] = useState('mine')
  const [status, setStatus] = useState('')
  const { data: rows = [] } = useQuery({
    queryKey: ['requests', scope, status],
    queryFn: () => listRequests({ scope, status: status || undefined }),
  })

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold text-brand-navy">Requests</h1>
      <div className="mb-4 flex gap-2">
        {(['mine', 'assigned'] as const).map((s) => (
          <button key={s} onClick={() => setScope(s)}
            className={`rounded px-3 py-1 text-sm ${scope === s ? 'bg-brand-blue text-white' : 'bg-slate-200 text-slate-700'}`}>
            {s === 'mine' ? 'My Requests' : 'Assigned to me'}
          </button>
        ))}
        <div className="w-48">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => <option key={s} value={s}>{s === '' ? 'All statuses' : s}</option>)}
          </Select>
        </div>
      </div>
      <RequestsTable rows={rows} />
    </div>
  )
}

export function RequestsTable({ rows }: { rows: RequestSummary[] }) {
  if (rows.length === 0) return <p className="text-sm text-slate-500">No requests.</p>
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b text-left text-slate-500">
          <th className="py-2">Number</th><th>Status</th><th>Division</th><th>Requestor</th><th>Total</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="border-b">
            <td className="py-2"><Link className="text-brand-blue hover:underline" to={`/requests/${r.id}`}>{r.number}</Link></td>
            <td>{r.status}</td>
            <td>{r.division_name ?? '—'}</td>
            <td>{r.requestor_name}</td>
            <td>${Number(r.total_cost ?? 0).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
