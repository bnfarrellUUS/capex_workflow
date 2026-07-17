// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ReportsPage from './ReportsPage'
import * as reportsApi from '../api/reports'
import { useMe } from '../auth/useMe'
import type { ReportSummary } from '../api/reports'

vi.mock('../api/reports')
vi.mock('../auth/useMe')

const SUMMARY: ReportSummary = {
  year: 2026,
  years: [2026, 2025],
  totals: { approved_total: '30000', approved_count: 2,
            pending_total: '5000', pending_count: 1, request_count: 4 },
  by_division: [{ division: '100 — Field Services', approved_total: '30000',
                  approved_count: 2, pending_total: '5000', pending_count: 1 }],
  by_month: Array.from({ length: 12 }, (_, i) => ({
    month: i + 1, approved_total: i === 2 ? '30000' : '0',
    approved_count: i === 2 ? 2 : 0, pending_total: '0', pending_count: 0 })),
  by_status: [
    { status: 'DRAFT', count: 1, total: '100' },
    { status: 'PENDING_L1', count: 1, total: '5000' },
    { status: 'PENDING_L2', count: 0, total: '0' },
    { status: 'PENDING_L3', count: 0, total: '0' },
    { status: 'APPROVED', count: 2, total: '30000' },
    { status: 'REJECTED', count: 0, total: '0' },
  ],
  cycle_time: { avg_days: 3.5, count: 2 },
}

function mockMe(roles: string[]) {
  vi.mocked(useMe).mockReturnValue({
    data: { id: 'u1', name: 'U', email: 'u@x.com', roles,
            division_id: null, must_change_password: false },
  } as ReturnType<typeof useMe>)
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/reports']}>
        <Routes>
          <Route path="/" element={<div>Dashboard Home</div>} />
          <Route path="/reports" element={<ReportsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(reportsApi.getReportSummary).mockResolvedValue(SUMMARY)
})

describe('ReportsPage', () => {
  it('redirects non-finance users to the dashboard', async () => {
    mockMe(['REQUESTOR'])
    renderPage()
    expect(await screen.findByText('Dashboard Home')).toBeInTheDocument()
    expect(reportsApi.getReportSummary).not.toHaveBeenCalled()
  })

  it('renders stats and tables for FINANCE', async () => {
    mockMe(['FINANCE'])
    renderPage()
    expect((await screen.findAllByText('$30,000')).length).toBeGreaterThan(0)
    expect(screen.getByText('100 — Field Services')).toBeInTheDocument()
    expect(screen.getByText('3.5')).toBeInTheDocument()
    expect(screen.getByText('Spend by division')).toBeInTheDocument()
    expect(screen.getByText('Spend by month')).toBeInTheDocument()
    expect(screen.getByText('By status')).toBeInTheDocument()
  })

  it('refetches when the year changes', async () => {
    mockMe(['ADMIN'])
    renderPage()
    await screen.findAllByText('$30,000')
    fireEvent.change(screen.getByLabelText('Year'), { target: { value: '2025' } })
    await waitFor(() =>
      expect(reportsApi.getReportSummary).toHaveBeenLastCalledWith(2025))
  })
})
