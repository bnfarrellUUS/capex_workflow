import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useMe } from '../auth/useMe'
import { logout } from '../api/auth'
import { Button } from './ui/Button'

const NAV = [
  { to: '/', label: 'Dashboard', roles: [] as string[], end: true },
  { to: '/requests/new', label: 'New Request', roles: [] as string[] },
  { to: '/requests', label: 'My Requests', roles: [] as string[] },
  { to: '/admin/users', label: 'Users', roles: ['ADMIN'] },
  { to: '/admin/divisions', label: 'Divisions', roles: ['ADMIN'] },
  { to: '/admin/thresholds', label: 'Approval Thresholds', roles: ['ADMIN'] },
  { to: '/profile', label: 'My Profile', roles: [] as string[] },
]

export function AppShell() {
  const { data: user } = useMe()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const roles = user?.roles ?? []
  const visible = NAV.filter((n) => n.roles.length === 0 || n.roles.some((r) => roles.includes(r)))

  async function handleLogout() {
    await logout()
    qc.clear()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 bg-brand-navy text-white">
        <div className="border-b border-white/15 p-4">
          <div className="font-bold leading-tight">United Uptime Services</div>
          <div className="text-xs text-brand-sky">CAPEX Tracking</div>
        </div>
        <nav className="space-y-1 p-2">
          {visible.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) =>
                `block rounded px-3 py-2 text-sm ${isActive ? 'bg-white/15' : 'hover:bg-white/10'}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-end gap-3 border-b bg-white px-6 py-3">
          <span className="text-sm text-slate-600">{user?.name}</span>
          <Button onClick={handleLogout} className="bg-slate-200 text-slate-800 hover:bg-slate-300">Sign out</Button>
        </header>
        <main className="flex-1 bg-slate-50 p-6"><Outlet /></main>
      </div>
    </div>
  )
}
