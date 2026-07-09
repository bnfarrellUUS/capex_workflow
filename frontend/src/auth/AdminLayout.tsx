import { Navigate, Outlet } from 'react-router-dom'
import { useMe } from './useMe'

export function AdminLayout() {
  const { data } = useMe()
  if (!data?.roles.includes('ADMIN')) return <Navigate to="/" replace />
  return <Outlet />
}
