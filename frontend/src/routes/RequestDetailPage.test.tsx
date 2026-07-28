// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import RequestDetailPage from './RequestDetailPage'
import type { CapexRequestData } from '../api/requests'

vi.mock('../api/requests', () => ({
  getRequest: vi.fn(),
  approveRequest: vi.fn(),
  rejectRequest: vi.fn(),
  resubmitRequest: vi.fn(),
  completeFinance: vi.fn(),
  deleteRequest: vi.fn(),
  uploadAttachment: vi.fn(),
  deleteAttachment: vi.fn(),
  attachmentUrl: (id: string, attId: string) => `/api/requests/${id}/attachments/${attId}`,
}))
vi.mock('../auth/useMe', () => ({
  useMe: () => ({ data: { id: 'approver-1', name: 'Approver', roles: ['APPROVER'], division_id: null } }),
}))
vi.mock('../api/requestSections', () => ({
  getHiddenSections: vi.fn(() => Promise.resolve([] as string[])),
  saveHiddenSections: vi.fn(() => Promise.resolve([] as string[])),
}))

import { getRequest } from '../api/requests'
import { getHiddenSections } from '../api/requestSections'

function makeRequest(): CapexRequestData {
  return {
    id: 'req-1', number: 'CX000042', status: 'PENDING_L1',
    division_id: 'div-1', request_date: '2026-07-13', description: 'Forklift',
    budgeted: true, replacement: false, health_safety: true, revenue_generating: false,
    environmental: false, competitive_bids: false, lease_recommended: false,
    justification: 'Because the old forklift died.',
    effect_on_operations: 'Warehouse throughput doubles.',
    asset_life: '7 years', irr_after_tax: '12.5', first_year_ebit: '5000',
    annual_savings: '9000', payback_years: '3.3', npv_savings: '20000',
    cost_autos_trucks: null, cost_machinery: null, cost_improvements: null,
    cost_furniture: null, cost_it_computer: null, cost_misc: null,
    asset_number: null, gl_account: null, useful_life_years: null, useful_life_months: null, in_service_date: null,
    total_cost: '30000', requestor_id: 'owner-1', assignee_id: null,
    requestor_name: 'Owner', assignee_name: null,
    current_approver_ids: ['approver-1'], current_approver_names: ['Approver'],
    division_name: '10 — Ops',
    finance_completed: false,
    equipment_items: [{ units: 1, condition: 'NEW', type: 'Lift', make: 'X', model: 'Y', cost: '30000' }],
    actions: [], attachments: [],
  }
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/requests/req-1']}>
        <Routes>
          <Route path="/requests/:id" element={<RequestDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RequestDetailPage — full request details', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRequest).mockResolvedValue(makeRequest())
  })

  it('is collapsed by default and expands to show all captured data', async () => {
    renderPage()
    await screen.findByText('Request CX000042')
    expect(screen.queryByText(/Because the old forklift died/)).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /Full request details/i }))

    expect(await screen.findByText(/Because the old forklift died/)).toBeInTheDocument()
    expect(screen.getByText(/Warehouse throughput doubles/)).toBeInTheDocument()
    expect(screen.getByText(/Budgeted:/)).toBeInTheDocument()
    expect(screen.getByText(/7 years/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Full request details/i }))
    expect(screen.queryByText(/Because the old forklift died/)).toBeNull()
  })
})

describe('RequestDetailPage — admin-hidden sections', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRequest).mockResolvedValue(makeRequest())
    vi.mocked(getHiddenSections).mockResolvedValue([])
  })

  it('omits a hidden section from Full request details', async () => {
    vi.mocked(getHiddenSections).mockResolvedValue(['economic'])
    renderPage()
    await screen.findByText('Request CX000042')
    fireEvent.click(screen.getByRole('button', { name: /Full request details/i }))

    expect(await screen.findByText(/Because the old forklift died/)).toBeInTheDocument()
    expect(screen.queryByText('Economic analysis')).toBeNull()
    expect(screen.queryByText(/7 years/)).toBeNull()
  })

  it('omits the justification and effect blocks when those sections are hidden', async () => {
    vi.mocked(getHiddenSections).mockResolvedValue(['description', 'effect_on_ops'])
    renderPage()
    await screen.findByText('Request CX000042')
    fireEvent.click(screen.getByRole('button', { name: /Full request details/i }))

    expect(await screen.findByText('Economic analysis')).toBeInTheDocument()
    expect(screen.queryByText(/Because the old forklift died/)).toBeNull()
    expect(screen.queryByText(/Warehouse throughput doubles/)).toBeNull()
  })

  it('omits the Asset details table when that section is hidden', async () => {
    vi.mocked(getHiddenSections).mockResolvedValue(['asset_details'])
    renderPage()
    await screen.findByText('Request CX000042')
    expect(screen.queryByText('Asset details')).toBeNull()
  })

  it('keeps the Attachments section, which FINANCE still needs after approval', async () => {
    vi.mocked(getHiddenSections).mockResolvedValue(['attachments'])
    renderPage()
    await screen.findByText('Request CX000042')
    expect(screen.getByText('Attachments')).toBeInTheDocument()
  })
})
