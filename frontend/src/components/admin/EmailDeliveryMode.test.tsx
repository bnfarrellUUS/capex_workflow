// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { EmailDeliveryMode } from './EmailDeliveryMode'
import * as apiMod from '../../api/emailTemplates'

vi.mock('../../api/emailTemplates')

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <EmailDeliveryMode />
    </QueryClientProvider>,
  )
}

describe('EmailDeliveryMode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiMod.getEmailSettings).mockResolvedValue({ mode: 'test', test_recipient: 'tester@uus.com' })
    vi.mocked(apiMod.saveEmailSettings).mockImplementation((b) => Promise.resolve(b))
  })

  it('shows the current mode and test recipient', async () => {
    renderPanel()
    await waitFor(() => expect(screen.getByDisplayValue('tester@uus.com')).toBeInTheDocument())
  })

  it('switching to Live requires confirmation and saves when confirmed', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderPanel()
    await waitFor(() => expect(screen.getByRole('button', { name: /Live/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Live/i }))
    expect(confirmSpy).toHaveBeenCalledOnce()
    await waitFor(() =>
      expect(apiMod.saveEmailSettings).toHaveBeenCalledWith(
        expect.objectContaining({ mode: 'live' })))
    confirmSpy.mockRestore()
  })

  it('does not switch to Live when confirmation is cancelled', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderPanel()
    await waitFor(() => expect(screen.getByRole('button', { name: /Live/i })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Live/i }))
    expect(confirmSpy).toHaveBeenCalledOnce()
    expect(apiMod.saveEmailSettings).not.toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('saves an edited test recipient (no confirm needed in Test mode)', async () => {
    renderPanel()
    await waitFor(() => expect(screen.getByDisplayValue('tester@uus.com')).toBeInTheDocument())
    fireEvent.change(screen.getByDisplayValue('tester@uus.com'), { target: { value: 'new@uus.com' } })
    fireEvent.click(screen.getByRole('button', { name: /^Save/i }))
    await waitFor(() =>
      expect(apiMod.saveEmailSettings).toHaveBeenCalledWith({ mode: 'test', test_recipient: 'new@uus.com' }))
  })
})
