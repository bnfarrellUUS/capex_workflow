import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  LayoutDashboard,
  FilePlus2,
  ListChecks,
  Users,
  Building2,
  SlidersHorizontal,
  UserCircle,
  LogOut,
  type LucideIcon,
} from 'lucide-react'
import { useMe } from '../auth/useMe'
import { logout } from '../api/auth'
import { Button } from './ui/Button'
import { ThemeToggle } from './ThemeToggle'
import { Logo } from './Logo'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  roles: string[]
  end?: boolean
  /** Extra paths that should also mark this item active (e.g. the wizard). */
  activePattern?: RegExp
}

const NAV_SECTIONS: { section: string; items: NavItem[] }[] = [
  {
    section: 'Overview',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, roles: [], end: true },
      { to: '/requests/new', label: 'New Request', icon: FilePlus2, roles: [], activePattern: /^\/requests\/[^/]+\/edit$/ },
      { to: '/requests', label: 'My Requests', icon: ListChecks, roles: [], end: true },
    ],
  },
  {
    section: 'Admin',
    items: [
      { to: '/admin/users', label: 'Users', icon: Users, roles: ['ADMIN'] },
      { to: '/admin/divisions', label: 'Divisions', icon: Building2, roles: ['ADMIN'] },
      { to: '/admin/thresholds', label: 'Approval Thresholds', icon: SlidersHorizontal, roles: ['ADMIN'] },
    ],
  },
  {
    section: 'Account',
    items: [{ to: '/profile', label: 'My Profile', icon: UserCircle, roles: [] }],
  },
]

const todayLabel = new Date().toISOString().slice(0, 10)

export function AppShell() {
  const { data: user } = useMe()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const qc = useQueryClient()
  const roles = user?.roles ?? []
  const can = (item: NavItem) => item.roles.length === 0 || item.roles.some((r) => roles.includes(r))

  const sections = NAV_SECTIONS.map((s) => ({ ...s, items: s.items.filter(can) })).filter(
    (s) => s.items.length > 0,
  )

  async function handleLogout() {
    await logout()
    qc.clear()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-screen bg-bg text-fg">
      <aside className="flex w-60 shrink-0 flex-col bg-sidebar text-sidebar-fg">
        <div className="flex items-center gap-3 border-b border-white/10 px-5 py-4">
          <Logo size={36} />
          <div>
            <div className="font-bold leading-tight text-white">United Uptime Services</div>
            <div className="text-xs text-brand-sky">CAPEX Flow</div>
          </div>
        </div>
        <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
          {sections.map((s) => (
            <div key={s.section}>
              <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-sidebar-muted">
                {s.section}
              </div>
              <div className="space-y-1">
                {s.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      className={({ isActive }) => {
                        const active = isActive || (item.activePattern?.test(pathname) ?? false)
                        return `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition ${
                          active
                            ? 'bg-accent text-white'
                            : 'text-sidebar-fg hover:bg-white/10 hover:text-white'
                        }`
                      }}
                    >
                      <Icon size={17} />
                      {item.label}
                    </NavLink>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-border bg-surface px-6 py-3">
          <div className="text-xs text-muted">Data last updated {todayLabel}</div>
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-fg">{user?.name}</span>
            <ThemeToggle />
            <Button variant="secondary" onClick={handleLogout}>
              <LogOut size={15} />
              Sign Out
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
