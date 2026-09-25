// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ChangePasswordPage from './ChangePasswordPage'

vi.mock('../api/auth', () => ({ setPassword: vi.fn(), logout: vi.fn() }))

import { setPassword, logout } from '../api/auth'
import { ApiError } from '../api/client'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/change-password']}>
        <Routes>
          <Route path="/change-password" element={<ChangePasswordPage />} />
          <Route path="/" element={<div>Home</div>} />
          <Route path="/login" element={<div>Login screen</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function fill(pw: string, confirm: string) {
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: pw } })
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: confirm } })
  fireEvent.click(screen.getByRole('button', { name: 'Set password' }))
}

beforeEach(() => { vi.clearAllMocks() })

describe('ChangePasswordPage', () => {
  it('rejects a password shorter than 8 characters without calling the API', async () => {
    renderPage()
    fill('short', 'short')
    expect(await screen.findByRole('alert')).toHaveTextContent('at least 8 characters')
    expect(setPassword).not.toHaveBeenCalled()
  })

  it('rejects a confirmation that does not match', async () => {
    renderPage()
    fill('LongEnough1', 'LongEnough2')
    expect(await screen.findByRole('alert')).toHaveTextContent('do not match')
    expect(setPassword).not.toHaveBeenCalled()
  })

  it('sets the password and goes home', async () => {
    vi.mocked(setPassword).mockResolvedValue({ id: 'u1' } as never)
    renderPage()
    fill('LongEnough1', 'LongEnough1')
    expect(await screen.findByText('Home')).toBeInTheDocument()
    expect(setPassword).toHaveBeenCalledWith('LongEnough1')
  })

  it('shows the server message when the API refuses', async () => {
    vi.mocked(setPassword).mockRejectedValue(new ApiError(400, 'Choose a different password.'))
    renderPage()
    fill('LongEnough1', 'LongEnough1')
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose a different password.')
  })

  it('signs out and goes to the login screen', async () => {
    vi.mocked(logout).mockResolvedValue()
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Sign out instead' }))
    expect(await screen.findByText('Login screen')).toBeInTheDocument()
  })

  it('says so when signing out fails, instead of doing nothing', async () => {
    vi.mocked(logout).mockRejectedValue(new TypeError('Failed to fetch'))
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Sign out instead' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not sign out')
    expect(screen.queryByText('Login screen')).toBeNull()
  })
})
