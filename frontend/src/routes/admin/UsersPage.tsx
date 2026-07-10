import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listUsers } from '../../api/users'
import { Button } from '../../components/ui/Button'
import { BrandCard } from '../../components/ui/BrandCard'

export default function UsersPage() {
  const { data: users, isLoading } = useQuery({ queryKey: ['users'], queryFn: listUsers })

  return (
    <BrandCard title="Users" subtitle="Accounts, roles & delegates"
      actions={<Link to="/admin/users/new"><Button>Add user</Button></Link>}
      bodyClassName="overflow-x-auto px-7 py-6">
      {isLoading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
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
      )}
    </BrandCard>
  )
}
