// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { DirectoryUser, PingDetail } from '../api/pings'
import { PingModal } from './PingModal'

vi.mock('../api/pings', () => ({
  createPing: vi.fn(),
  pingDirectory: vi.fn(),
  pingSuggestions: vi.fn(),
}))
import { createPing, pingDirectory, pingSuggestions } from '../api/pings'

const USERS: DirectoryUser[] = [
  { id: 'u1', name: 'Dana Whitfield', email: 'dana@x.com', roles: ['FINANCE'], division_name: null },
  { id: 'u2', name: 'Ann Reader', email: 'ann@x.com', roles: ['APPROVER'], division_name: '100 — Ops' },
]

function detailStub(): PingDetail {
  return {
    id: 'p1', note: 'x', sender: { id: 'u9', name: 'Me' },
    created_at: '2026-09-09T12:00:00+00:00', request_id: null, request: null,
    recipients: [], reply_count: 0, unread_replies: 0, unread_for_me: false,
    last_activity_at: '2026-09-09T12:00:00+00:00', completed_at: null, done_by: null,
    search_blob: '', replies: [],
  }
}

function renderModal(init: Parameters<typeof PingModal>[0]['init'] = {}, onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <PingModal init={init} onClose={onClose} />
    </QueryClientProvider>,
  )
  return onClose
}

const noteBox = () => screen.getAllByRole('textbox').find((el) => el.tagName === 'TEXTAREA')!

describe('PingModal', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the directory and counts a checked recipient toward N/25', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    renderModal()
    expect(await screen.findByText('Dana Whitfield')).toBeInTheDocument()
    expect(screen.getByText('0/25 recipients')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    expect(screen.getByText('1/25 recipients')).toBeInTheDocument()
  })

  it('disables Send with no note or no recipients', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    renderModal()
    await screen.findByText('Dana Whitfield')
    const send = screen.getByRole('button', { name: /^send$/i })
    expect(send).toBeDisabled()
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    expect(send).toBeDisabled()                       // recipient, no note
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    fireEvent.change(noteBox(), { target: { value: 'hi' } })
    expect(send).toBeDisabled()                       // note, no recipient
  })

  it('Send posts the picked recipients, note and request id, then closes', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    vi.mocked(pingSuggestions).mockResolvedValue([])
    vi.mocked(createPing).mockResolvedValue(detailStub())
    const onClose = renderModal({ request: { id: 'req-1', number: 'CX000042' } })
    await screen.findByText('Dana Whitfield')
    expect(screen.getByText('CX000042')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('checkbox', { name: /dana whitfield/i }))
    fireEvent.change(noteBox(), { target: { value: 'Please take a look' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    await waitFor(() => expect(createPing).toHaveBeenCalledWith({
      recipient_ids: ['u1'], note: 'Please take a look', request_id: 'req-1',
    }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('clearing the request chip sends request_id null', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    vi.mocked(pingSuggestions).mockResolvedValue([])
    vi.mocked(createPing).mockResolvedValue(detailStub())
    renderModal({ request: { id: 'req-1', number: 'CX000042' } })
    await screen.findByText('CX000042')
    fireEvent.click(screen.getByRole('button', { name: /remove request/i }))
    expect(screen.queryByText('CX000042')).toBeNull()
    fireEvent.click(screen.getByRole('checkbox', { name: /dana whitfield/i }))
    fireEvent.change(noteBox(), { target: { value: 'General question' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    await waitFor(() => expect(createPing).toHaveBeenCalledWith(
      expect.objectContaining({ request_id: null })))
  })

  it('with a request, suggested users render first under Suggested and only once', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    vi.mocked(pingSuggestions).mockResolvedValue([USERS[1]])
    renderModal({ request: { id: 'req-1', number: 'CX000042' } })
    expect(await screen.findByText('Suggested')).toBeInTheDocument()
    expect(pingSuggestions).toHaveBeenCalledWith('req-1')
    const rows = screen.getAllByRole('checkbox').map((el) => el.closest('label'))
    expect(screen.getAllByText('Ann Reader')).toHaveLength(1)
    const ann = rows.find((r) => r?.textContent?.includes('Ann Reader'))
    const dana = rows.find((r) => r?.textContent?.includes('Dana Whitfield'))
    expect(rows.indexOf(ann!)).toBeLessThan(rows.indexOf(dana!))
  })

  it('without a request, pingSuggestions is never called', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    renderModal()
    await screen.findByText('Dana Whitfield')
    expect(pingSuggestions).not.toHaveBeenCalled()
  })

  it('shows the server error when Send fails', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    vi.mocked(createPing).mockRejectedValue(new Error('A ping needs a note.'))
    renderModal()
    await screen.findByText('Dana Whitfield')
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    fireEvent.change(noteBox(), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('A ping needs a note.')
  })
})
