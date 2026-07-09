import { useQuery } from '@tanstack/react-query'
import { useMe } from '../auth/useMe'
import { listRequests } from '../api/requests'
import { RequestsTable } from './RequestsListPage'

export default function DashboardPage() {
  const { data: user } = useMe()
  const { data: approvals = [] } = useQuery({
    queryKey: ['requests', 'assigned', ''],
    queryFn: () => listRequests({ scope: 'assigned' }),
  })
  return (
    <div className="space-y-6">
      <div>
        <h1 className="mb-1 text-2xl font-semibold text-brand-navy">Dashboard</h1>
        <p className="text-slate-600">Welcome, {user?.name}.</p>
      </div>
      <section>
        <h2 className="mb-2 font-semibold">My approvals</h2>
        <RequestsTable rows={approvals} />
      </section>
    </div>
  )
}
