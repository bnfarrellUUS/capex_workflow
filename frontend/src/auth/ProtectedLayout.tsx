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
  // An SSO session has no password to change, so sending them to
  // /change-password would ask them to invent one nothing uses. The server
  // skips the same gate in app/__init__.py.
  if (data.must_change_password && data.auth_method !== 'sso')
    return <Navigate to="/change-password" replace />
  return <AppShell />
}
