import { Routes, Route } from 'react-router-dom'
import LoginPage from './routes/LoginPage'
import DashboardPage from './routes/DashboardPage'
import { ProtectedLayout } from './auth/ProtectedLayout'
import { AdminLayout } from './auth/AdminLayout'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route element={<AdminLayout />}>
          {/* admin routes added in later tasks */}
        </Route>
      </Route>
    </Routes>
  )
}
