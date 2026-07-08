import { Routes, Route } from 'react-router-dom'
import LoginPage from './routes/LoginPage'
import DashboardPage from './routes/DashboardPage'
import { RequireAuth } from './auth/RequireAuth'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RequireAuth><DashboardPage /></RequireAuth>} />
    </Routes>
  )
}
