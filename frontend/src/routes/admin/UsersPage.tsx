import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listUsers } from '../../api/users'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'

export default function UsersPage() {
  const { data: users, isLoading } = useQuery({ queryKey: ['users'], queryFn: listUsers })

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-fg">Users</h1>
        <Link to="/admin/users/new"><Button>Add user</Button></Link>
      </div>
      {isLoading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <Card className="overflow-x-auto p-5">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
              <th className="py-2 pr-4 font-semibold">Username</th><th className="pr-4 font-semibold">Name</th><th className="pr-4 font-semibold">Email</th>
              <th className="pr-4 font-semibold">Roles</th><th className="pr-4 font-semibold">Active</th><th></th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id} className="border-b border-border last:border-0 hover:bg-surface-2">
                <td className="py-2.5 pr-4">{u.username}</td>
                <td className="pr-4">{u.name}</td>
                <td className="pr-4">{u.email}</td>
                <td className="pr-4">{u.roles.join(', ')}</td>
                <td className="pr-4">{u.active ? 'Yes' : 'No'}</td>
                <td><Link className="text-accent hover:underline" to={`/admin/users/${u.id}`}>Edit</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
        </Card>
      )}
    </div>
  )
}
