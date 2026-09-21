// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/auth', () => ({
  getAuthConfig: vi.fn(),
  login: vi.fn(),
}))
import { getAuthConfig } from '../api/auth'
import LoginPage from './LoginPage'

function renderPage(initial = '/login') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initial]}>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LoginPage sign-in modes', () => {
  beforeEach(() => { vi.mocked(getAuthConfig).mockReset() })

  it('shows neither form while the config is still loading', () => {
    // Defaulting to the password form would flash a box that then vanishes,
    // which reads as breakage and trains users to type credentials into a
    // disappearing form.
    vi.mocked(getAuthConfig).mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.getByText(/loading sign-in options/i)).toBeInTheDocument()
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /microsoft/i })).not.toBeInTheDocument()
  })

  it('offers only the Microsoft button when SSO is on', async () => {
    vi.mocked(getAuthConfig).mockResolvedValue({ ok: true, sso_enabled: true })
    renderPage()
    expect(await screen.findByRole('button', { name: /sign in with microsoft/i }))
      .toBeInTheDocument()
    expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument()
  })

  it('offers only the password form when SSO is off', async () => {
    vi.mocked(getAuthConfig).mockResolvedValue({ ok: true, sso_enabled: false })
    renderPage()
    expect(await screen.findByLabelText('Password')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /microsoft/i })).not.toBeInTheDocument()
  })

  it('falls back to the password form when the config call fails', async () => {
    // If the config call fails the server is probably down, and the password
    // form at least produces a comprehensible error.
    vi.mocked(getAuthConfig).mockRejectedValue(new Error('offline'))
    renderPage()
    expect(await screen.findByLabelText('Password')).toBeInTheDocument()
  })
})

describe('LoginPage sso_error messages', () => {
  beforeEach(() => {
    vi.mocked(getAuthConfig).mockReset()
    vi.mocked(getAuthConfig).mockResolvedValue({ ok: true, sso_enabled: true })
  })

  it.each([
    ['not_in_group', /authorized security group/i, /contact it/i],
    ['no_groups_claim', /no group information/i, /contact it/i],
    ['unknown_user', /isn't set up in capri/i, /admin/i],
    ['inactive_user', /deactivated/i, /admin/i],
    ['identity_mismatch', /doesn't match the account on file/i, /contact it/i],
    ['auth_failed', /failed or was cancelled/i, /try again/i],
  ])('explains %s and names who fixes it', async (code, message, fixer) => {
    renderPage(`/login?sso_error=${code}`)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(message)
    expect(alert).toHaveTextContent(fixer)
  })

  it('falls back to a generic message for an unknown code', async () => {
    renderPage('/login?sso_error=something_new')
    expect(await screen.findByRole('alert'))
      .toHaveTextContent(/microsoft sign-in failed/i)
  })

  it('shows no alert when there is no sso_error', async () => {
    renderPage('/login')
    await screen.findByRole('button', { name: /microsoft/i })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
