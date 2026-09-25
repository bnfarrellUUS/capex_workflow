// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import UserEditPage from './UserEditPage'

vi.mock('../../api/users', () => ({
  listUsers: vi.fn(() => Promise.resolve([
    { id: 'u1', email: 'r@x.com', name: 'Rita', roles: ['REQUESTOR'], active: true, division_id: null },
  ])),
  updateUser: vi.fn(), resetUserPassword: vi.fn(), deleteUser: vi.fn(),
}))
vi.mock('../../api/divisions', () => ({ listDivisions: vi.fn(() => Promise.resolve([])) }))

import { resetUserPassword, deleteUser } from '../../api/users'
import { ApiError } from '../../api/client'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/admin/users/u1']}>
        <Routes>
          <Route path="/admin/users/:id" element={<UserEditPage />} />
          <Route path="/admin/users" element={<div>Users list</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => { vi.restoreAllMocks(); vi.clearAllMocks() })

describe('UserEditPage — reset to default password', () => {
  it('does nothing when the confirm is cancelled', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Reset to default password' }))
    expect(window.confirm).toHaveBeenCalledWith('Reset r@x.com to the default password?')
    expect(resetUserPassword).not.toHaveBeenCalled()
  })

  it('resets on confirm and says the user was signed out', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(resetUserPassword).mockResolvedValue()
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Reset to default password' }))
    expect(await screen.findByText(/has been signed out/)).toBeInTheDocument()
    expect(resetUserPassword).toHaveBeenCalledWith('u1')
  })

  it('shows the server message on an API error', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(resetUserPassword).mockRejectedValue(new ApiError(404, 'User not found.'))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Reset to default password' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('User not found.')
  })

  it('shows a generic message when the request fails outright', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(resetUserPassword).mockRejectedValue(new TypeError('Failed to fetch'))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Reset to default password' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Reset failed.')
  })
})

describe('UserEditPage — delete', () => {
  it('shows a generic message when the request fails outright', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(deleteUser).mockRejectedValue(new TypeError('Failed to fetch'))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Delete user' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Delete failed.')
  })

  it('returns to the users list after deleting', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(deleteUser).mockResolvedValue()
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Delete user' }))
    expect(await screen.findByText('Users list')).toBeInTheDocument()
  })
})
