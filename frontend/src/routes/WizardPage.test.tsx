// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import WizardPage from './WizardPage'
import type { CapexRequestData } from '../api/requests'

vi.mock('../api/requests', () => ({
  getRequest: vi.fn(),
  updateDraft: vi.fn(() => Promise.resolve({})),
  submitRequest: vi.fn(() => Promise.resolve({})),
  resubmitRequest: vi.fn(() => Promise.resolve({})),
}))
vi.mock('../api/divisions', () => ({
  listDivisions: vi.fn(() => Promise.resolve([])),
}))

import { getRequest, submitRequest, resubmitRequest } from '../api/requests'

function makeRequest(status: string): CapexRequestData {
  return {
    id: 'req-1', number: 'CX000042', status,
    division_id: 'div-1', request_date: '2026-07-13', description: 'Forklift',
    budgeted: false, replacement: false, health_safety: false, revenue_generating: false,
    environmental: false, competitive_bids: false, lease_recommended: false,
    justification: '', effect_on_operations: '',
    asset_life: null, irr_after_tax: null, first_year_ebit: null,
    annual_savings: null, payback_years: null, npv_savings: null,
    total_cost: '30000', requestor_id: 'me', assignee_id: null,
    requestor_name: 'Me', assignee_name: null,
    current_approver_ids: [], current_approver_names: [], division_name: '10 — Ops',
    finance_completed: false,
    equipment_items: [{ units: 1, condition: 'NEW', type: 'Lift', make: 'X', model: 'Y', cost: '30000' }],
    actions: [], attachments: [],
  }
}

function renderWizard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/requests/req-1/edit']}>
        <Routes>
          <Route path="/requests/:id/edit" element={<WizardPage />} />
          <Route path="/requests/:id" element={<div>Detail</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function submitFromReviewStep() {
  await screen.findByText('Request CX000042')
  fireEvent.click(await screen.findByRole('button', { name: /Review/ }))
  fireEvent.click(await screen.findByRole('button', { name: /for approval/i }))
}

describe('WizardPage submit routing', () => {
  beforeEach(() => vi.clearAllMocks())

  it('resubmits a REJECTED request via the resubmit endpoint', async () => {
    vi.mocked(getRequest).mockResolvedValue(makeRequest('REJECTED'))
    renderWizard()
    await submitFromReviewStep()
    await waitFor(() => expect(resubmitRequest).toHaveBeenCalledWith('req-1'))
    expect(submitRequest).not.toHaveBeenCalled()
  })

  it('submits a DRAFT request via the submit endpoint', async () => {
    vi.mocked(getRequest).mockResolvedValue(makeRequest('DRAFT'))
    renderWizard()
    await submitFromReviewStep()
    await waitFor(() => expect(submitRequest).toHaveBeenCalledWith('req-1'))
    expect(resubmitRequest).not.toHaveBeenCalled()
  })
})
