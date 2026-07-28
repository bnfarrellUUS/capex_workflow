// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RequestSectionsPage from './RequestSectionsPage'

vi.mock('../../api/requestSections', () => ({
  getHiddenSections: vi.fn(() => Promise.resolve([] as string[])),
  saveHiddenSections: vi.fn((hidden: string[]) => Promise.resolve(hidden)),
}))

import { getHiddenSections, saveHiddenSections } from '../../api/requestSections'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <RequestSectionsPage />
    </QueryClientProvider>,
  )
}

/** The step number (or '—') shown on a section's row. */
function stepNumberFor(label: string): string | null {
  const row = screen.getByText(label).closest('[data-section-row]')
  return row?.querySelector('[data-step-number]')?.textContent ?? null
}

describe('RequestSectionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getHiddenSections).mockResolvedValue([])
    vi.mocked(saveHiddenSections).mockImplementation((hidden) => Promise.resolve(hidden))
  })

  it('numbers all seven sections when nothing is hidden', async () => {
    renderPage()
    await screen.findByText('Basic Info')
    expect(stepNumberFor('Basic Info')).toBe('1')
    expect(stepNumberFor('Economic')).toBe('5')
    expect(stepNumberFor('Review')).toBe('7')
  })

  it('offers no toggle for the always-visible sections', async () => {
    renderPage()
    await screen.findByText('Basic Info')
    expect(screen.getAllByText('(always)')).toHaveLength(2)
    expect(screen.getByRole('checkbox', { name: /Economic/ })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: /Basic Info/ })).toBeNull()
    expect(screen.queryByRole('checkbox', { name: /Review/ })).toBeNull()
  })

  it('reflects the saved config on load', async () => {
    vi.mocked(getHiddenSections).mockResolvedValue(['economic'])
    renderPage()
    await screen.findByText('Basic Info')
    expect(screen.getByRole('checkbox', { name: /Economic/ })).not.toBeChecked()
    expect(stepNumberFor('Economic')).toBe('—')
    expect(stepNumberFor('Attachments')).toBe('5')
  })

  it('renumbers live when a section is toggled off, before saving', async () => {
    renderPage()
    await screen.findByText('Basic Info')
    fireEvent.click(screen.getByRole('checkbox', { name: /Economic/ }))
    expect(stepNumberFor('Economic')).toBe('—')
    expect(stepNumberFor('Attachments')).toBe('5')
    expect(stepNumberFor('Review')).toBe('6')
    expect(saveHiddenSections).not.toHaveBeenCalled()
  })

  it('saves the hidden keys', async () => {
    renderPage()
    await screen.findByText('Basic Info')
    fireEvent.click(screen.getByRole('checkbox', { name: /Economic/ }))
    fireEvent.click(screen.getByRole('button', { name: /Save/i }))
    await waitFor(() => expect(saveHiddenSections).toHaveBeenCalledWith(['economic']))
    expect(await screen.findByText(/Saved/)).toBeInTheDocument()
  })

  it('saves an empty list when a section is shown again', async () => {
    vi.mocked(getHiddenSections).mockResolvedValue(['economic'])
    renderPage()
    await screen.findByText('Basic Info')
    fireEvent.click(screen.getByRole('checkbox', { name: /Economic/ }))
    fireEvent.click(screen.getByRole('button', { name: /Save/i }))
    await waitFor(() => expect(saveHiddenSections).toHaveBeenCalledWith([]))
  })

  it('warns that hiding Asset Details zeroes the total and routes at Level 1', async () => {
    renderPage()
    await screen.findByText('Basic Info')
    const row = screen.getByText('Asset Details').closest('[data-section-row]')
    expect(row?.textContent).toMatch(/Level 1/)
  })
})
