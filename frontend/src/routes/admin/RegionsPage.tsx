import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listRegions, type Region } from '../../api/regions'
import { Button } from '../../components/ui/Button'
import { BrandCard } from '../../components/ui/BrandCard'
import { SortHeader } from '../../components/ui/SortHeader'
import { SearchIcon } from '../../components/ActionIcons'
import { sortRows, type SortDir, type SortValue } from './tableSort'

type SortKey = 'name' | 'vps' | 'divisions' | 'active'

const GETTERS: Record<SortKey, (r: Region) => SortValue> = {
  name: (r) => r.name,
  vps: (r) => r.vp_approver_ids.length,
  divisions: (r) => r.division_count ?? 0,
  active: (r) => r.active,
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'vps', label: 'VPs' },
  { key: 'divisions', label: 'Divisions' },
  { key: 'active', label: 'Active' },
]

export default function RegionsPage() {
  const { data: regions, isLoading } = useQuery({ queryKey: ['regions'], queryFn: listRegions })
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir } | null>(null)

  const toggleSort = (key: SortKey) =>
    setSort((s) => ({ key, dir: s?.key === key && s.dir === 'asc' ? 'desc' : 'asc' }))

  const q = query.trim().toLowerCase()
  let rows = regions ?? []
  if (q) {
    rows = rows.filter((r) =>
      [r.name, ...(r.vp_approver_names ?? [])].some((f) => f?.toLowerCase().includes(q)),
    )
  }
  if (sort) rows = sortRows(rows, GETTERS[sort.key], sort.dir)

  return (
    <BrandCard title="Regions" subtitle="Regions & their VP (Level-2) approver pools" mark="regions"
      actions={<Link to="/admin/regions/new"><Button>Add region</Button></Link>}
      bodyClassName="overflow-x-auto px-7 py-6">
      <div className="relative mb-4">
        <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted">
          <SearchIcon size={16} />
        </span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search regions…"
          aria-label="Search regions"
          className="w-56 rounded-md border border-border bg-surface py-1.5 pl-8 pr-3 text-sm text-fg outline-none focus:border-accent"
        />
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
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border last:border-0 hover:bg-surface-2">
                  <td className="py-2.5 pr-4">{r.name}</td>
                  <td className="pr-4">{r.vp_approver_names?.join(', ') || '—'}</td>
                  <td className="pr-4">{r.division_count ?? 0}</td>
                  <td className="pr-4">{r.active ? 'Yes' : 'No'}</td>
                  <td><Link className="text-accent hover:underline" to={`/admin/regions/${r.id}`}>Edit</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="mt-3 text-sm text-muted">No regions match.</p>}
        </>
      )}
    </BrandCard>
  )
}
