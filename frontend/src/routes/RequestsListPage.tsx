import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { listRequests, type RequestSummary } from '../api/requests'
import { Select } from '../components/ui/Select'
import { BrandCard } from '../components/ui/BrandCard'
import { StatusBadge } from '../components/ui/Badge'
import { SearchIcon, FilterIcon, ViewIcon } from '../components/ActionIcons'
import { sortRequests, filterRequests, type SortDir, type SortKey } from './requestsSort'

const STATUSES = ['', 'DRAFT', 'PENDING_L1', 'PENDING_L2', 'PENDING_L3', 'APPROVED', 'REJECTED']

export default function RequestsListPage() {
  const [scope, setScope] = useState('mine')
  const [status, setStatus] = useState('')
  const [query, setQuery] = useState('')
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
      <div className="relative">
        <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted">
          <SearchIcon size={16} />
        </span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search requests…"
          aria-label="Search requests"
          className="w-56 rounded-md border border-border bg-surface py-1.5 pl-8 pr-3 text-sm text-fg outline-none focus:border-accent"
        />
      </div>
      <div className="flex items-center gap-1.5 text-muted">
        <FilterIcon size={16} />
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
    </div>
  )

  return (
    <BrandCard title="Requests" subtitle="Capital expenditure requests" mark="requests" subheader={filters}>
      <RequestsTable rows={filterRequests(rows, query)} />
    </BrandCard>
  )
}

const COLUMNS: { key: SortKey; label: string; right?: boolean }[] = [
  { key: 'number', label: 'Number' },
  { key: 'status', label: 'Status' },
  { key: 'division_name', label: 'Division' },
  { key: 'requestor_name', label: 'Requestor' },
  { key: 'total_cost', label: 'Total', right: true },
]

export function RequestsTable({ rows }: { rows: RequestSummary[] }) {
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir } | null>(null)
  if (rows.length === 0) return <p className="text-sm text-muted">No requests.</p>
  const sorted = sort ? sortRequests(rows, sort.key, sort.dir) : rows

  const toggleSort = (key: SortKey) =>
    setSort((s) => ({ key, dir: s?.key === key && s.dir === 'asc' ? 'desc' : 'asc' }))

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-brand-sky/25 text-left text-xs uppercase tracking-wide text-brand-navy dark:bg-brand-sky/10 dark:text-brand-sky [&>th]:py-1.5 [&>th:first-child]:pl-2 [&>th:last-child]:pr-2">
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                aria-sort={sort?.key === col.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                className={`py-2 pr-4 font-semibold ${col.right ? 'text-right' : ''}`}
              >
                <button
                  onClick={() => toggleSort(col.key)}
                  className="group inline-flex items-center gap-1 uppercase tracking-wide hover:text-accent"
                >
                  {col.label}
                  {sort?.key === col.key ? (
                    sort.dir === 'asc' ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronUp className="h-3.5 w-3.5 opacity-0 group-hover:opacity-40" />
                  )}
                </button>
              </th>
            ))}
            <th className="py-2 pr-2 text-right font-semibold"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
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
              <td className="py-2.5 pr-2 text-right">
                <Link
                  to={`/requests/${r.id}`}
                  aria-label={`View ${r.number}`}
                  title="View"
                  className="inline-flex text-muted hover:text-accent"
                >
                  <ViewIcon size={18} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
