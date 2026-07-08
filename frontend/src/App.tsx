import { Routes, Route } from 'react-router-dom'
import LoginPage from './routes/LoginPage'
import DashboardPage from './routes/DashboardPage'
import { ProtectedLayout } from './auth/ProtectedLayout'
import { AdminLayout } from './auth/AdminLayout'
import UsersPage from './routes/admin/UsersPage'
import UserNewPage from './routes/admin/UserNewPage'
import UserEditPage from './routes/admin/UserEditPage'
import DivisionsPage from './routes/admin/DivisionsPage'
import DivisionNewPage from './routes/admin/DivisionNewPage'
import DivisionEditPage from './routes/admin/DivisionEditPage'
import ThresholdsPage from './routes/admin/ThresholdsPage'
import ProfilePage from './routes/ProfilePage'
import NewRequestPage from './routes/NewRequestPage'
import WizardPage from './routes/WizardPage'
import RequestDetailPage from './routes/RequestDetailPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/requests/new" element={<NewRequestPage />} />
        <Route path="/requests/:id/edit" element={<WizardPage />} />
        <Route path="/requests/:id" element={<RequestDetailPage />} />
        <Route element={<AdminLayout />}>
          <Route path="/admin/users" element={<UsersPage />} />
          <Route path="/admin/users/new" element={<UserNewPage />} />
          <Route path="/admin/users/:id" element={<UserEditPage />} />
          <Route path="/admin/divisions" element={<DivisionsPage />} />
          <Route path="/admin/divisions/new" element={<DivisionNewPage />} />
          <Route path="/admin/divisions/:id" element={<DivisionEditPage />} />
          <Route path="/admin/thresholds" element={<ThresholdsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
