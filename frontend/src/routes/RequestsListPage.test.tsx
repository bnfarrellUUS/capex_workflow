// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RequestsListPage from './RequestsListPage'
import * as reqApi from '../api/requests'
import { useMe } from '../auth/useMe'

vi.mock('../api/requests', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/requests')>()
  return { ...mod, listRequests: vi.fn(), downloadRequestsExport: vi.fn() }
})
vi.mock('../auth/useMe')
vi.mock('../api/pings', () => ({
  createPing: vi.fn(), pingDirectory: vi.fn(() => Promise.resolve([])),
  pingSuggestions: vi.fn(() => Promise.resolve([])),
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RequestsListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function mockMe(roles: string[]) {
  vi.mocked(useMe).mockReturnValue({
    data: { id: 'u1', name: 'U', email: 'u@x.com', roles,
            division_id: null, must_change_password: false },
  } as ReturnType<typeof useMe>)
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(reqApi.listRequests).mockResolvedValue([])
})

describe('RequestsListPage', () => {
  it('hides the All tab for a plain requestor', async () => {
    mockMe(['REQUESTOR'])
    renderPage()
    await waitFor(() => expect(reqApi.listRequests).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: 'All' })).not.toBeInTheDocument()
  })

  it('shows the All tab for FINANCE and lists with scope=all', async () => {
    mockMe(['FINANCE'])
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'All' }))
    await waitFor(() => expect(reqApi.listRequests).toHaveBeenLastCalledWith(
      { scope: 'all', status: undefined }))
  })

  it('exports with the current scope, status and search text', async () => {
    mockMe(['FINANCE'])
    vi.mocked(reqApi.downloadRequestsExport).mockResolvedValue()
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'All' }))
    fireEvent.change(screen.getByLabelText('Search requests'),
      { target: { value: 'CX0001' } })
    fireEvent.click(screen.getByRole('button', { name: /Export/i }))
    await waitFor(() => expect(reqApi.downloadRequestsExport)
      .toHaveBeenCalledWith({ scope: 'all', status: '', q: 'CX0001' }))
  })

  it('each row has an accent Ping icon that opens the modal for that request', async () => {
    mockMe(['REQUESTOR'])
    vi.mocked(reqApi.listRequests).mockResolvedValue([{
      id: 'req-1', number: 'CX000042', status: 'DRAFT', total_cost: '100',
      division_name: '100 — Ops', requestor_name: 'Owner', assignee_name: null, created_at: null,
    }])
    renderPage()
    const ping = await screen.findByRole('button', { name: 'Ping about CX000042' })
    expect(ping.className).toContain('text-accent')
    fireEvent.click(ping)
    expect(screen.getByRole('dialog', { name: /new ping/i })).toBeInTheDocument()
    expect(screen.getAllByText('CX000042').length).toBeGreaterThan(1)   // row + modal chip
  })

  it('offers Decided by me to everyone and lists with scope=decided', async () => {
    mockMe(['REQUESTOR'])
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Decided by me' }))
    await waitFor(() => expect(reqApi.listRequests).toHaveBeenLastCalledWith(
      { scope: 'decided', status: undefined }))
  })

  it('marks a stuck request with "No approver"', async () => {
    mockMe(['ADMIN'])
    vi.mocked(reqApi.listRequests).mockResolvedValue([{
      id: 'req-1', number: 'CX000042', status: 'PENDING_L1', total_cost: '100',
      division_name: '100 — Ops', requestor_name: 'Owner', assignee_name: null, created_at: null,
      stuck: true,
    }])
    renderPage()
    expect(await screen.findByText('No approver')).toBeInTheDocument()
  })

  it('offers the Stuck filter to admins only', async () => {
    mockMe(['FINANCE'])
    const { unmount } = renderPage()
    await waitFor(() => expect(reqApi.listRequests).toHaveBeenCalled())
    expect(screen.queryByRole('option', { name: /Stuck/ })).toBeNull()
    unmount()

    mockMe(['ADMIN'])
    renderPage()
    fireEvent.change(await screen.findByDisplayValue('All statuses'), { target: { value: 'STUCK' } })
    await waitFor(() => expect(reqApi.listRequests).toHaveBeenLastCalledWith(
      { scope: 'mine', status: 'STUCK' }))
  })
})
