// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { PingDetail } from './PingDetail'
import type { PingDetail as PingDetailType } from '../api/pings'

vi.mock('../api/pings', () => ({
  getPing: vi.fn(),
  replyToPing: vi.fn(),
  markPingDone: vi.fn(),
  reopenPing: vi.fn(),
}))
import { getPing, replyToPing, markPingDone, reopenPing } from '../api/pings'

vi.mock('../auth/useMe', () => ({
  useMe: () => ({ data: { id: 'u1', name: 'Me', email: 'me@x.com', roles: ['APPROVER'],
                          division_id: null, must_change_password: false } }),
}))

function baseDetail(overrides: Partial<PingDetailType> = {}): PingDetailType {
  return {
    id: 'p1',
    note: 'Please confirm the GL account.',
    sender: { id: 'u2', name: 'Sam Sender' },
    created_at: '2026-09-09T12:00:00+00:00',
    request_id: null,
    request: null,
    recipients: [
      { user_id: 'u1', name: 'Me', email: 'me@x.com', read_at: null, completed_at: null },
      { user_id: 'u3', name: 'Ann', email: 'a@x.com', read_at: null, completed_at: null },
    ],
    reply_count: 1,
    unread_replies: 0,
    unread_for_me: false,
    last_activity_at: '2026-09-09T12:05:00+00:00',
    completed_at: null,
    done_by: null,
    search_blob: 'Looking now.',
    replies: [
      { id: 'r1', note: 'Looking now.', created_at: '2026-09-09T12:05:00+00:00',
        sender: { id: 'u3', name: 'Ann' } },
    ],
    ...overrides,
  }
}

const REQ = {
  id: 'req-1', number: 'CX000042', status: 'PENDING_L1', division_name: '100 — Ops',
  requestor_name: 'Owner', total_cost: '30000', visible: true,
}

function renderDetail(props: Partial<Parameters<typeof PingDetail>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <PingDetail id="p1" {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PingDetail', () => {
  it('renders the note, replies and roster', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail())
    renderDetail()
    expect(await screen.findByText('Please confirm the GL account.')).toBeInTheDocument()
    expect(screen.getByText('Looking now.')).toBeInTheDocument()
    expect(screen.getByText('Sam Sender')).toBeInTheDocument()
    expect(screen.getAllByText('Ann').length).toBeGreaterThan(0)
  })

  it('renders the request chip as a link when visible, and fires onNavigate', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail({ request_id: 'req-1', request: REQ }))
    const onNavigate = vi.fn()
    renderDetail({ onNavigate })
    const link = await screen.findByRole('link', { name: /CX000042/ })
    expect(link).toHaveAttribute('href', '/requests/req-1')
    expect(screen.getByText('Pending L1')).toBeInTheDocument()
    fireEvent.click(link)
    expect(onNavigate).toHaveBeenCalled()
  })

  it('renders the request chip as plain text when not visible', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail({
      request_id: 'req-1', request: { ...REQ, visible: false },
    }))
    renderDetail()
    await screen.findByText(/CX000042/)
    expect(screen.queryByRole('link', { name: /CX000042/ })).toBeNull()
  })

  it('Send calls replyToPing with the typed note', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail())
    vi.mocked(replyToPing).mockResolvedValue(baseDetail())
    renderDetail()
    await screen.findByText('Please confirm the GL account.')
    fireEvent.change(screen.getByPlaceholderText(/reply/i), { target: { value: 'On it.' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    await waitFor(() => expect(replyToPing).toHaveBeenCalledWith('p1', 'On it.'))
  })

  it('Mark done calls markPingDone when the viewer is on the roster', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail())
    vi.mocked(markPingDone).mockResolvedValue(baseDetail())
    renderDetail()
    await screen.findByText('Please confirm the GL account.')
    fireEvent.click(screen.getByRole('button', { name: /mark done/i }))
    await waitFor(() => expect(markPingDone).toHaveBeenCalledWith('p1'))
  })

  it('offers neither Mark done nor Reopen when the viewer is off the roster', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail({
      recipients: [{ user_id: 'u3', name: 'Ann', email: 'a@x.com', read_at: null, completed_at: null }],
    }))
    renderDetail()
    await screen.findByText('Please confirm the GL account.')
    expect(screen.queryByRole('button', { name: /mark done/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /^reopen$/i })).toBeNull()
  })

  it('offers Reopen and shows Done by once the viewer has ticked it', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail({
      completed_at: '2026-09-09T13:00:00+00:00',
      done_by: 'Me',
      recipients: [
        { user_id: 'u1', name: 'Me', email: 'me@x.com', read_at: null,
          completed_at: '2026-09-09T13:00:00+00:00' },
      ],
    }))
    vi.mocked(reopenPing).mockResolvedValue(baseDetail())
    renderDetail()
    await screen.findByText('Please confirm the GL account.')
    expect(screen.getByText(/Done by Me/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^reopen$/i }))
    await waitFor(() => expect(reopenPing).toHaveBeenCalledWith('p1'))
  })

  it('renders an error with the back button still usable when the fetch fails', async () => {
    vi.mocked(getPing).mockRejectedValue(new Error('boom'))
    const onBack = vi.fn()
    renderDetail({ onBack })
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /back/i }))
    expect(onBack).toHaveBeenCalled()
  })
})
