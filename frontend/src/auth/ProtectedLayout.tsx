import { Navigate } from 'react-router-dom'
import { useMe } from './useMe'
import { AppShell } from '../components/AppShell'

export function ProtectedLayout() {
  const { data, isLoading, isError } = useMe()
  if (isLoading) return <div className="p-6 text-sm text-muted">Loading…</div>
  if (isError || !data) return <Navigate to="/login" replace />
  return <AppShell />
}
