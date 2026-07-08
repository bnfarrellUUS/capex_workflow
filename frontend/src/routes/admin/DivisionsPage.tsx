import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listDivisions } from '../../api/divisions'
import { Button } from '../../components/ui/Button'

export default function DivisionsPage() {
  const { data: divisions, isLoading } = useQuery({ queryKey: ['divisions'], queryFn: listDivisions })
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-brand-navy">Divisions</h1>
        <Link to="/admin/divisions/new"><Button>Add division</Button></Link>
      </div>
      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b text-left text-slate-500">
              <th className="py-2">Number</th><th>Name</th><th>Active</th><th></th>
            </tr>
          </thead>
          <tbody>
            {divisions?.map((d) => (
              <tr key={d.id} className="border-b">
                <td className="py-2">{d.number}</td>
                <td>{d.name}</td>
                <td>{d.active ? 'Yes' : 'No'}</td>
                <td><Link className="text-brand-blue hover:underline" to={`/admin/divisions/${d.id}`}>Edit</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
