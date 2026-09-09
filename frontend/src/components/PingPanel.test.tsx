// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PingSummary } from '../api/pings'
import { PingPanel } from './PingPanel'

vi.mock('../api/pings', () => ({
  listPings: vi.fn(), getPing: vi.fn(), replyToPing: vi.fn(), markPingDone: vi.fn(),
  reopenPing: vi.fn(), createPing: vi.fn(), pingDirectory: vi.fn(), pingSuggestions: vi.fn(),
}))
import { listPings, getPing } from '../api/pings'
vi.mock('../auth/useMe', () => ({
  useMe: () => ({ data: { id: 'u2', name: 'Ann', email: 'a@x.com', roles: ['APPROVER'],
                          division_id: null, must_change_password: false } }),
}))

function makePing(overrides: Partial<PingSummary> = {}): PingSummary {
  return {
    id: 'p1', note: 'Root note about the forklift.', sender: { id: 'u1', name: 'Sam Sender' },
    created_at: '2026-09-09T12:00:00+00:00', request_id: null, request: null,
    recipients: [{ user_id: 'u2', name: 'Ann', email: 'a@x.com', read_at: null, completed_at: null }],
    reply_count: 1, unread_replies: 0, unread_for_me: false,
    last_activity_at: '2026-09-09T12:05:00+00:00', completed_at: null, done_by: null,
    search_blob: '', ...overrides,
  }
}

function renderPanel(onClose: () => void = () => {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><PingPanel onClose={onClose} /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PingPanel', () => {
  it('lists inbox cards and switches to Sent', async () => {
    vi.mocked(listPings).mockResolvedValue([makePing()])
    renderPanel()
    expect(await screen.findByText('Root note about the forklift.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^sent$/i }))
    expect(listPings).toHaveBeenCalledWith('sent')
  })

  it('finds a conversation by a phrase said only in a reply', async () => {
    vi.mocked(listPings).mockResolvedValue([
      makePing({ id: 'p1', search_blob: 'the phrase nobody else says' }),
      makePing({ id: 'p2', note: 'Unrelated ping.' }),
    ])
    renderPanel()
    await screen.findByText('Root note about the forklift.')
    fireEvent.change(screen.getByLabelText(/search messages/i), { target: { value: 'nobody else says' } })
    expect(screen.getByText('Root note about the forklift.')).toBeInTheDocument()
    expect(screen.queryByText('Unrelated ping.')).toBeNull()
  })

  it('the Open filter hides done pings and the Done chip counts them', async () => {
    vi.mocked(listPings).mockResolvedValue([
      makePing({ id: 'p1' }),
      makePing({ id: 'p2', note: 'Finished one.', completed_at: '2026-09-09T13:00:00+00:00', done_by: 'Ann' }),
    ])
    renderPanel()
    await screen.findByText('Root note about the forklift.')
    expect(screen.queryByText('Finished one.')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /^done/i }))
    expect(screen.getByText('Finished one.')).toBeInTheDocument()
  })

  it('closes the panel when the detail\'s request link is followed', async () => {
    vi.mocked(listPings).mockResolvedValue([makePing({ request_id: 'req-1' })])
    vi.mocked(getPing).mockResolvedValue({
      ...makePing({ request_id: 'req-1' }), replies: [],
      request: { id: 'req-1', number: 'CX000042', status: 'DRAFT', division_name: null,
                 requestor_name: 'Owner', total_cost: '0', visible: true },
    })
    const onClose = vi.fn()
    renderPanel(onClose)
    fireEvent.click(await screen.findByText('Root note about the forklift.'))
    fireEvent.click(await screen.findByRole('link', { name: /CX000042/ }))
    expect(onClose).toHaveBeenCalled()
  })
})
