import { useMe } from '../auth/useMe'

export default function DashboardPage() {
  const { data: user } = useMe()
  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold text-brand-navy">Dashboard</h1>
      <p className="text-slate-600">Welcome, {user?.name}. Request queues arrive in a later milestone.</p>
    </div>
  )
}
