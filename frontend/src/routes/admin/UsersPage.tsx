import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listUsers } from '../../api/users'
import { Button } from '../../components/ui/Button'

export default function UsersPage() {
  const { data: users, isLoading } = useQuery({ queryKey: ['users'], queryFn: listUsers })

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-brand-navy">Users</h1>
        <Link to="/admin/users/new"><Button>Add user</Button></Link>
      </div>
      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b text-left text-slate-500">
              <th className="py-2">Username</th><th>Name</th><th>Email</th>
              <th>Roles</th><th>Active</th><th></th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id} className="border-b">
                <td className="py-2">{u.username}</td>
                <td>{u.name}</td>
                <td>{u.email}</td>
                <td>{u.roles.join(', ')}</td>
                <td>{u.active ? 'Yes' : 'No'}</td>
                <td><Link className="text-brand-blue hover:underline" to={`/admin/users/${u.id}`}>Edit</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
