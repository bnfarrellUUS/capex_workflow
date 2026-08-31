import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listRegions } from '../../api/regions'
import { Button } from '../../components/ui/Button'
import { BrandCard } from '../../components/ui/BrandCard'

export default function RegionsPage() {
  const { data: regions, isLoading } = useQuery({ queryKey: ['regions'], queryFn: listRegions })
  return (
    <BrandCard title="Regions" subtitle="Regions & their VP (Level-2) approver pools" mark="regions"
      actions={<Link to="/admin/regions/new"><Button>Add region</Button></Link>}
      bodyClassName="overflow-x-auto px-7 py-6">
      {isLoading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-brand-sky/25 text-left text-xs uppercase tracking-wide text-brand-navy dark:bg-brand-sky/10 dark:text-brand-sky [&>th]:py-1.5 [&>th:first-child]:pl-2 [&>th:last-child]:pr-2">
              <th className="py-2 pr-4 font-semibold">Name</th><th className="pr-4 font-semibold">VPs</th><th className="pr-4 font-semibold">Divisions</th><th className="pr-4 font-semibold">Active</th><th></th>
            </tr>
          </thead>
          <tbody>
            {regions?.map((r) => (
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
      )}
    </BrandCard>
  )
}
