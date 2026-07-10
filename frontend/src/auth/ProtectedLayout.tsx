import { Navigate, useLocation } from 'react-router-dom'
import { useMe } from './useMe'
import { AppShell } from '../components/AppShell'
import { loginPathWithNext } from './loginRedirect'

export function ProtectedLayout() {
  const { data, isLoading, isError } = useMe()
  const location = useLocation()
  if (isLoading) return <div className="p-6 text-sm text-muted">Loading…</div>
  if (isError || !data) {
    return <Navigate to={loginPathWithNext(location.pathname, location.search)} replace />
  }
  return <AppShell />
}
