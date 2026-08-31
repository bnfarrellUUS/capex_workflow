import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listDivisions, type Division } from '../../api/divisions'
import { listRegions } from '../../api/regions'
import { Button } from '../../components/ui/Button'
import { Select } from '../../components/ui/Select'
import { BrandCard } from '../../components/ui/BrandCard'
import { SortHeader } from '../../components/ui/SortHeader'
import { SearchIcon, FilterIcon } from '../../components/ActionIcons'
import { sortRows, type SortDir, type SortValue } from './tableSort'

type SortKey = 'number' | 'name' | 'region_name' | 'active'

const GETTERS: Record<SortKey, (d: Division) => SortValue> = {
  number: (d) => d.number,
  name: (d) => d.name,
  region_name: (d) => d.region_name,
  active: (d) => d.active,
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'number', label: 'Number' },
  { key: 'name', label: 'Name' },
  { key: 'region_name', label: 'Region' },
  { key: 'active', label: 'Active' },
]

export default function DivisionsPage() {
  const { data: divisions, isLoading } = useQuery({ queryKey: ['divisions'], queryFn: listDivisions })
  const { data: regions = [] } = useQuery({ queryKey: ['regions'], queryFn: listRegions })
  const [query, setQuery] = useState('')
  const [regionFilter, setRegionFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir } | null>(null)

  const toggleSort = (key: SortKey) =>
    setSort((s) => ({ key, dir: s?.key === key && s.dir === 'asc' ? 'desc' : 'asc' }))

  const q = query.trim().toLowerCase()
  let rows = divisions ?? []
  if (q) rows = rows.filter((d) => [d.number, d.name, d.region_name].some((f) => f?.toLowerCase().includes(q)))
  if (regionFilter === 'none') rows = rows.filter((d) => !d.region_id)
  else if (regionFilter) rows = rows.filter((d) => d.region_id === regionFilter)
  if (activeFilter === 'active') rows = rows.filter((d) => d.active)
  else if (activeFilter === 'inactive') rows = rows.filter((d) => !d.active)
  if (sort) rows = sortRows(rows, GETTERS[sort.key], sort.dir)

  return (
    <BrandCard title="Divisions" subtitle="Divisions & their Level-1 approver pools" mark="divisions"
      actions={<Link to="/admin/divisions/new"><Button>Add division</Button></Link>}
      bodyClassName="overflow-x-auto px-7 py-6">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative">
          <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted">
            <SearchIcon size={16} />
          </span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search divisions…"
            aria-label="Search divisions"
            className="w-56 rounded-md border border-border bg-surface py-1.5 pl-8 pr-3 text-sm text-fg outline-none focus:border-accent"
          />
        </div>
        <div className="flex items-center gap-1.5 text-muted">
          <FilterIcon size={16} />
          <div className="w-44">
            <Select value={regionFilter} onChange={(e) => setRegionFilter(e.target.value)} aria-label="Filter by region">
              <option value="">All regions</option>
              {regions.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
              <option value="none">No region</option>
            </Select>
          </div>
          <div className="w-32">
            <Select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)} aria-label="Filter by active">
              <option value="">All</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </Select>
          </div>
        </div>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-brand-sky/25 text-left text-xs uppercase tracking-wide text-brand-navy dark:bg-brand-sky/10 dark:text-brand-sky [&>th]:py-1.5 [&>th:first-child]:pl-2 [&>th:last-child]:pr-2">
                {COLUMNS.map((col) => (
                  <SortHeader key={col.key} label={col.label} active={sort?.key === col.key}
                    dir={sort?.dir ?? 'asc'} onClick={() => toggleSort(col.key)} />
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.id} className="border-b border-border last:border-0 hover:bg-surface-2">
                  <td className="py-2.5 pr-4">{d.number}</td>
                  <td className="pr-4">{d.name}</td>
                  <td className="pr-4">{d.region_name ?? '—'}</td>
                  <td className="pr-4">{d.active ? 'Yes' : 'No'}</td>
                  <td><Link className="text-accent hover:underline" to={`/admin/divisions/${d.id}`}>Edit</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="mt-3 text-sm text-muted">No divisions match.</p>}
        </>
      )}
    </BrandCard>
  )
}
