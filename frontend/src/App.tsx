import { Routes, Route } from 'react-router-dom'
import LoginPage from './routes/LoginPage'
import DashboardPage from './routes/DashboardPage'
import { ProtectedLayout } from './auth/ProtectedLayout'
import { AdminLayout } from './auth/AdminLayout'
import UsersPage from './routes/admin/UsersPage'
import UserNewPage from './routes/admin/UserNewPage'
import UserEditPage from './routes/admin/UserEditPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route element={<AdminLayout />}>
          <Route path="/admin/users" element={<UsersPage />} />
          <Route path="/admin/users/new" element={<UserNewPage />} />
          <Route path="/admin/users/:id" element={<UserEditPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
