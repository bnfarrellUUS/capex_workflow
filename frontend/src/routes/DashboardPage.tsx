import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useMe } from '../auth/useMe'
import { logout } from '../api/auth'
import { Button } from '../components/ui/Button'

export default function DashboardPage() {
  const { data: user } = useMe()
  const navigate = useNavigate()
  const qc = useQueryClient()

  async function handleLogout() {
    await logout()
    qc.clear()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between border-b bg-brand-navy px-6 py-3 text-white">
        <div className="font-bold">United Uptime Services · CAPEX Tracking</div>
        <div className="flex items-center gap-3 text-sm">
          <span>{user?.name}</span>
          <Button onClick={handleLogout} className="bg-white/10">Sign out</Button>
        </div>
      </header>
      <main className="p-6">
        <h1 className="mb-2 text-2xl font-semibold text-brand-navy">Dashboard</h1>
        <p className="text-slate-600">Welcome, {user?.name}. Request queues arrive in a later milestone.</p>
      </main>
    </div>
  )
}
