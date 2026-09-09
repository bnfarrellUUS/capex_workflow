// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PingDetail as PingDetailType, PingSummary } from '../api/pings'
import { formatActionDate } from './formatDate'
import MessagesPage from './MessagesPage'

vi.mock('../api/pings', () => ({
  listPings: vi.fn(), getPing: vi.fn(), replyToPing: vi.fn(), markPingDone: vi.fn(),
  reopenPing: vi.fn(), createPing: vi.fn(), pingDirectory: vi.fn(), pingSuggestions: vi.fn(),
}))
import { listPings, getPing } from '../api/pings'
vi.mock('../auth/useMe', () => ({
  useMe: () => ({ data: { id: 'u2', name: 'Me', email: 'me@x.com', roles: ['APPROVER'],
                          division_id: null, must_change_password: false } }),
}))

const ping: PingSummary = {
  id: 'p1', note: 'GL account on the forklift looks wrong.',
  sender: { id: 'u1', name: 'Dana Whitfield' }, created_at: '2026-09-08T14:22:00+00:00',
  request_id: 'req-1',
  request: { id: 'req-1', number: 'CX000042', status: 'PENDING_L1', division_name: '100 — Ops',
             requestor_name: 'Owner', total_cost: '30000', visible: true },
  recipients: [{ user_id: 'u2', name: 'Me', email: 'me@x.com', read_at: null, completed_at: null }],
  reply_count: 2, unread_replies: 1, unread_for_me: true,
  last_activity_at: '2026-09-08T14:22:00+00:00', completed_at: null, done_by: null, search_blob: '',
}
const readPing: PingSummary = {
  ...ping, id: 'p2', request_id: null, request: null, sender: { id: 'u3', name: 'Ann Reader' },
  unread_for_me: false, note: 'A second, already-read ping.',
}
const detail: PingDetailType = { ...ping, replies: [] }

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}><MemoryRouter><MessagesPage /></MemoryRouter></QueryClientProvider>,
  )
}

describe('MessagesPage', () => {
  it('lists pings in a table with the column headers', async () => {
    vi.mocked(listPings).mockResolvedValue([ping])
    renderPage()
    expect(await screen.findByText('Dana Whitfield')).toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument()
    for (const h of ['From / To', 'Ping', 'Request', 'Replies', 'Status', 'Last activity']) {
      expect(screen.getByText(h)).toBeInTheDocument()
    }
    expect(screen.getByText('CX000042')).toBeInTheDocument()
    expect(screen.getByText('unread')).toBeInTheDocument()
  })

  it('offers Inbox and Sent as tabs, and switching fetches the other box', async () => {
    vi.mocked(listPings).mockResolvedValue([ping])
    renderPage()
    const sent = await screen.findByRole('tab', { name: /sent/i })
    expect(screen.getByRole('tab', { name: /inbox/i })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(sent)
    expect(listPings).toHaveBeenCalledWith('sent')
    expect(sent).toHaveAttribute('aria-selected', 'true')
  })

  it('only bolds the sender cell for an unread ping', async () => {
    vi.mocked(listPings).mockResolvedValue([ping, readPing])
    renderPage()
    const unreadCell = (await screen.findByText('Dana Whitfield')).closest('td')!
    const readCell = screen.getByText('Ann Reader').closest('td')!
    expect(unreadCell.className).toContain('font-semibold')
    expect(readCell.className).not.toContain('font-semibold')
  })

  it('searches by person, note, request number or reply text', async () => {
    vi.mocked(listPings).mockResolvedValue([ping, readPing])
    renderPage()
    await screen.findByText('Dana Whitfield')
    fireEvent.change(screen.getByLabelText('Search messages'), { target: { value: 'cx000042' } })
    expect(screen.getByText('Dana Whitfield')).toBeInTheDocument()
    expect(screen.queryByText('Ann Reader')).toBeNull()
  })

  it('formats last activity through formatActionDate, not the raw ISO string', async () => {
    vi.mocked(listPings).mockResolvedValue([ping])
    renderPage()
    expect(await screen.findByText(formatActionDate(ping.last_activity_at))).toBeInTheDocument()
    expect(screen.queryByText(ping.last_activity_at)).toBeNull()
  })

  it('clicking a row expands the detail inline and clicking again collapses it', async () => {
    vi.mocked(listPings).mockResolvedValue([ping])
    vi.mocked(getPing).mockResolvedValue(detail)
    renderPage()
    const row = (await screen.findByText(/GL account on the forklift/)).closest('tr')!
    fireEvent.click(row)
    expect(await screen.findByText(/GL account on the forklift looks wrong/, { selector: 'p' }))
      .toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(row)
    expect(screen.queryByText(/GL account on the forklift looks wrong/, { selector: 'p' })).toBeNull()
  })

  it('has a New Ping button that opens the modal', async () => {
    vi.mocked(listPings).mockResolvedValue([])
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /new ping/i }))
    expect(screen.getByRole('dialog', { name: /new ping/i })).toBeInTheDocument()
  })
})
