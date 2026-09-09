// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PingBell } from './PingBell'

vi.mock('../api/pings', () => ({ pingUnreadCount: vi.fn() }))
import { pingUnreadCount } from '../api/pings'

function renderBell() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <PingBell onClick={() => {}} />
    </QueryClientProvider>,
  )
}

describe('PingBell', () => {
  it('shows the unread count', async () => {
    vi.mocked(pingUnreadCount).mockResolvedValue(3)
    renderBell()
    expect(await screen.findByText('3')).toBeInTheDocument()
  })

  it('caps the badge at 99+', async () => {
    vi.mocked(pingUnreadCount).mockResolvedValue(120)
    renderBell()
    expect(await screen.findByText('99+')).toBeInTheDocument()
  })

  it('shows no badge at zero', async () => {
    vi.mocked(pingUnreadCount).mockResolvedValue(0)
    renderBell()
    expect(await screen.findByRole('button', { name: /messages/i })).toBeInTheDocument()
    expect(screen.queryByTestId('ping-badge')).toBeNull()
  })
})
