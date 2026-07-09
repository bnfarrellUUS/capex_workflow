import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listDivisions } from '../../api/divisions'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'

export default function DivisionsPage() {
  const { data: divisions, isLoading } = useQuery({ queryKey: ['divisions'], queryFn: listDivisions })
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-fg">Divisions</h1>
        <Link to="/admin/divisions/new"><Button>Add division</Button></Link>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <Card className="overflow-x-auto p-5">
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
        </Card>
      )}
    </div>
  )
}
