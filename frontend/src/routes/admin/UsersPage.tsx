import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listUsers, type AdminUser } from '../../api/users'
import { Button } from '../../components/ui/Button'
import { BrandCard } from '../../components/ui/BrandCard'
import { SortHeader } from '../../components/ui/SortHeader'
import { SearchIcon } from '../../components/ActionIcons'
import { sortRows, type SortDir, type SortValue } from './tableSort'

type SortKey = 'name' | 'email' | 'roles' | 'active'

const GETTERS: Record<SortKey, (u: AdminUser) => SortValue> = {
  name: (u) => u.name,
  email: (u) => u.email,
  roles: (u) => u.roles.join(', '),
  active: (u) => u.active,
}

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
  { key: 'roles', label: 'Roles' },
  { key: 'active', label: 'Active' },
]

export default function UsersPage() {
  const { data: users, isLoading } = useQuery({ queryKey: ['users'], queryFn: listUsers })
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir } | null>(null)

  const toggleSort = (key: SortKey) =>
    setSort((s) => ({ key, dir: s?.key === key && s.dir === 'asc' ? 'desc' : 'asc' }))

  const q = query.trim().toLowerCase()
  let rows = users ?? []
  if (q) {
    rows = rows.filter((u) =>
      [u.name, u.email, u.roles.join(', ')].some((f) => f?.toLowerCase().includes(q)),
    )
  }
  if (sort) rows = sortRows(rows, GETTERS[sort.key], sort.dir)

  return (
    <BrandCard title="Users" subtitle="Accounts, roles & delegates" mark="users"
      actions={<Link to="/admin/users/new"><Button>Add user</Button></Link>}
      bodyClassName="overflow-x-auto px-7 py-6">
      <div className="relative mb-4">
        <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted">
          <SearchIcon size={16} />
        </span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search users…"
          aria-label="Search users"
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
              {rows.map((u) => (
                <tr key={u.id} className="border-b border-border last:border-0 hover:bg-surface-2">
                  <td className="py-2.5 pr-4">{u.name}</td>
                  <td className="pr-4">{u.email}</td>
                  <td className="pr-4">{u.roles.join(', ')}</td>
                  <td className="pr-4">{u.active ? 'Yes' : 'No'}</td>
                  <td><Link className="text-accent hover:underline" to={`/admin/users/${u.id}`}>Edit</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="mt-3 text-sm text-muted">No users match.</p>}
        </>
      )}
    </BrandCard>
  )
}
