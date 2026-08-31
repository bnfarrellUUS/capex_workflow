// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DivisionsPage from './DivisionsPage'
import type { Division } from '../../api/divisions'
import type { Region } from '../../api/regions'

const DIVISIONS: Division[] = [
  { id: 'd1', number: '10', name: 'Corporate', active: true, l1_approver_ids: [], region_id: 'r2', region_name: 'East' },
  { id: 'd2', number: '2', name: 'Airside', active: false, l1_approver_ids: [], region_id: 'r1', region_name: 'West' },
  { id: 'd3', number: '5', name: 'Marine', active: true, l1_approver_ids: [], region_id: null, region_name: null },
]
const REGIONS: Region[] = [
  { id: 'r1', name: 'West', active: true, vp_approver_ids: [] },
  { id: 'r2', name: 'East', active: true, vp_approver_ids: [] },
]

vi.mock('../../api/divisions', () => ({ listDivisions: vi.fn() }))
vi.mock('../../api/regions', () => ({ listRegions: vi.fn() }))

import { listDivisions } from '../../api/divisions'
import { listRegions } from '../../api/regions'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <DivisionsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** Division numbers of the visible rows, in table order. */
function visibleNumbers(): string[] {
  return screen.getAllByRole('row').slice(1).map((row) => row.querySelector('td')?.textContent ?? '')
}

describe('DivisionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(listDivisions).mockResolvedValue(DIVISIONS)
    vi.mocked(listRegions).mockResolvedValue(REGIONS)
  })

  it('lists every division with its region', async () => {
    renderPage()
    expect(await screen.findByText('Corporate')).toBeInTheDocument()
    expect(visibleNumbers()).toEqual(['10', '2', '5'])
    expect(screen.getByText('Corporate').closest('tr')?.textContent).toContain('East')
  })

  it('search matches number, name, and region', async () => {
    renderPage()
    await screen.findByText('Corporate')
    const search = screen.getByRole('searchbox', { name: /search divisions/i })
    fireEvent.change(search, { target: { value: 'west' } })
    expect(visibleNumbers()).toEqual(['2'])
    fireEvent.change(search, { target: { value: 'marine' } })
    expect(visibleNumbers()).toEqual(['5'])
    fireEvent.change(search, { target: { value: '10' } })
    expect(visibleNumbers()).toEqual(['10'])
  })

  it('filters by region, including divisions with no region', async () => {
    renderPage()
    await screen.findByText('Corporate')
    const region = screen.getByRole('combobox', { name: /filter by region/i })
    fireEvent.change(region, { target: { value: 'r1' } })
    expect(visibleNumbers()).toEqual(['2'])
    fireEvent.change(region, { target: { value: 'none' } })
    expect(visibleNumbers()).toEqual(['5'])
    fireEvent.change(region, { target: { value: '' } })
    expect(visibleNumbers()).toEqual(['10', '2', '5'])
  })

  it('filters by active state', async () => {
    renderPage()
    await screen.findByText('Corporate')
    const active = screen.getByRole('combobox', { name: /filter by active/i })
    fireEvent.change(active, { target: { value: 'inactive' } })
    expect(visibleNumbers()).toEqual(['2'])
    fireEvent.change(active, { target: { value: 'active' } })
    expect(visibleNumbers()).toEqual(['10', '5'])
  })

  it('sorts by number naturally and flips direction on second click', async () => {
    renderPage()
    await screen.findByText('Corporate')
    const header = screen.getByRole('button', { name: /^number$/i })
    fireEvent.click(header)
    expect(visibleNumbers()).toEqual(['2', '5', '10'])
    fireEvent.click(header)
    expect(visibleNumbers()).toEqual(['10', '5', '2'])
  })

  it('sorts by region with blanks last', async () => {
    renderPage()
    await screen.findByText('Corporate')
    fireEvent.click(screen.getByRole('button', { name: /^region$/i }))
    expect(visibleNumbers()).toEqual(['10', '2', '5'])
  })
})
