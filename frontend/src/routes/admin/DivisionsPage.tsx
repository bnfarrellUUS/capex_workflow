import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listDivisions } from '../../api/divisions'
import { Button } from '../../components/ui/Button'
import { BrandCard } from '../../components/ui/BrandCard'

export default function DivisionsPage() {
  const { data: divisions, isLoading } = useQuery({ queryKey: ['divisions'], queryFn: listDivisions })
  return (
    <BrandCard title="Divisions" subtitle="Divisions & their Level-1 approver pools" mark="divisions"
      actions={<Link to="/admin/divisions/new"><Button>Add division</Button></Link>}
      bodyClassName="overflow-x-auto px-7 py-6">
      {isLoading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
              <th className="py-2 pr-4 font-semibold">Number</th><th className="pr-4 font-semibold">Name</th><th className="pr-4 font-semibold">Active</th><th></th>
            </tr>
          </thead>
          <tbody>
            {divisions?.map((d) => (
              <tr key={d.id} className="border-b border-border last:border-0 hover:bg-surface-2">
                <td className="py-2.5 pr-4">{d.number}</td>
                <td className="pr-4">{d.name}</td>
                <td className="pr-4">{d.active ? 'Yes' : 'No'}</td>
                <td><Link className="text-accent hover:underline" to={`/admin/divisions/${d.id}`}>Edit</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </BrandCard>
  )
}
