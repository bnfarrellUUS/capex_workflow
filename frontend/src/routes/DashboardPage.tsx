import { useQuery } from '@tanstack/react-query'
import { useMe } from '../auth/useMe'
import { listRequests, type RequestSummary } from '../api/requests'
import { StatCard } from '../components/ui/Card'
import { BrandCard } from '../components/ui/BrandCard'
import { RequestsTable } from './RequestsListPage'

const PENDING = ['PENDING_L1', 'PENDING_L2', 'PENDING_L3']

function money(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`
  return `$${n.toLocaleString()}`
}

function sumCost(rows: RequestSummary[]): number {
  return rows.reduce((acc, r) => acc + Number(r.total_cost ?? 0), 0)
}

export default function DashboardPage() {
  const { data: user } = useMe()
  const { data: approvals = [] } = useQuery({
    queryKey: ['requests', 'assigned', ''],
    queryFn: () => listRequests({ scope: 'assigned' }),
  })
  const { data: mine = [] } = useQuery({
    queryKey: ['requests', 'mine', ''],
    queryFn: () => listRequests({ scope: 'mine' }),
  })

  const pendingMine = approvals.filter((r) => PENDING.includes(r.status))
  const myOpen = mine.filter((r) => r.status !== 'APPROVED' && r.status !== 'REJECTED')
  const myApproved = mine.filter((r) => r.status === 'APPROVED')

  return (
    <BrandCard title="Dashboard" subtitle={`Welcome, ${user?.name ?? ''}`} mark="dashboard">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Pending My Approval"
          value={pendingMine.length}
          sub={`${money(sumCost(pendingMine))} total`}
          accent
        />
        <StatCard
          label="My Open Requests"
          value={myOpen.length}
          sub={`${mine.length} total submitted`}
        />
        <StatCard label="Total CAPEX (my requests)" value={money(sumCost(mine))} sub={`${mine.length} requests`} />
        <StatCard label="Approved" value={myApproved.length} sub={`${money(sumCost(myApproved))} total`} />
      </div>

      <h2 className="mb-3 mt-6 font-semibold text-fg">My Approvals</h2>
      <RequestsTable rows={approvals} />
    </BrandCard>
  )
}
