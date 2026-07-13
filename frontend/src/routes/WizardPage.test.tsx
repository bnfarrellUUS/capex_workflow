// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import WizardPage from './WizardPage'
import type { CapexRequestData } from '../api/requests'

vi.mock('../api/requests', () => ({
  getRequest: vi.fn(),
  createDraft: vi.fn(() => Promise.resolve({ id: 'new-1' })),
  updateDraft: vi.fn(() => Promise.resolve({})),
  submitRequest: vi.fn(() => Promise.resolve({})),
  resubmitRequest: vi.fn(() => Promise.resolve({})),
  uploadAttachment: vi.fn(() => Promise.resolve({})),
  deleteAttachment: vi.fn(() => Promise.resolve({})),
  attachmentUrl: (id: string, attId: string) => `/api/requests/${id}/attachments/${attId}`,
}))
vi.mock('../api/divisions', () => ({
  listDivisions: vi.fn(() => Promise.resolve([])),
}))
vi.mock('../auth/useMe', () => ({
  useMe: () => ({ data: { id: 'me', name: 'Me', roles: ['REQUESTOR'], division_id: 'div-1' } }),
}))

import { getRequest, createDraft, updateDraft, submitRequest, resubmitRequest, uploadAttachment } from '../api/requests'

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

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/requests/new" element={<WizardPage />} />
          <Route path="/requests/:id/edit" element={<WizardPage />} />
          <Route path="/requests/:id" element={<div>Detail</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('WizardPage — submit routing (existing draft)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRequest).mockResolvedValue(makeRequest('DRAFT'))
  })

  async function submitFromReviewStep() {
    await screen.findByText('Request CX000042')
    fireEvent.click(await screen.findByRole('button', { name: /Review/ }))
    fireEvent.click(await screen.findByRole('button', { name: /for approval/i }))
  }

  it('resubmits a REJECTED request via the resubmit endpoint', async () => {
    vi.mocked(getRequest).mockResolvedValue(makeRequest('REJECTED'))
    renderAt('/requests/req-1/edit')
    await submitFromReviewStep()
    await waitFor(() => expect(resubmitRequest).toHaveBeenCalledWith('req-1'))
    expect(submitRequest).not.toHaveBeenCalled()
  })

  it('submits a DRAFT request via the submit endpoint', async () => {
    renderAt('/requests/req-1/edit')
    await submitFromReviewStep()
    await waitFor(() => expect(submitRequest).toHaveBeenCalledWith('req-1'))
    expect(resubmitRequest).not.toHaveBeenCalled()
  })
})

describe('WizardPage — new request defers draft creation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRequest).mockResolvedValue(makeRequest('DRAFT'))
  })

  it('does not create a draft just by opening the New Request screen', async () => {
    renderAt('/requests/new')
    await screen.findByText('New Request')
    await new Promise((r) => setTimeout(r, 0))
    expect(createDraft).not.toHaveBeenCalled()
  })

  it('does not create a draft when clicking Next', async () => {
    renderAt('/requests/new')
    await screen.findByText('New Request')
    fireEvent.click(await screen.findByRole('button', { name: /^Next$/ }))
    await new Promise((r) => setTimeout(r, 0))
    expect(createDraft).not.toHaveBeenCalled()
  })

  it('creates then updates the draft on Save Draft', async () => {
    renderAt('/requests/new')
    await screen.findByText('New Request')
    fireEvent.click(await screen.findByRole('button', { name: /Save Draft/i }))
    await waitFor(() => expect(createDraft).toHaveBeenCalledOnce())
    await waitFor(() => expect(updateDraft).toHaveBeenCalledWith('new-1', expect.anything()))
  })

  it('creates, updates, then submits on Submit', async () => {
    renderAt('/requests/new')
    await screen.findByText('New Request')
    fireEvent.click(await screen.findByRole('button', { name: /Review/ }))
    fireEvent.click(await screen.findByRole('button', { name: /for approval/i }))
    await waitFor(() => expect(createDraft).toHaveBeenCalledOnce())
    await waitFor(() => expect(updateDraft).toHaveBeenCalledWith('new-1', expect.anything()))
    await waitFor(() => expect(submitRequest).toHaveBeenCalledWith('new-1'))
  })

  it('uploading on the Attachments step creates the draft then attaches', async () => {
    renderAt('/requests/new')
    await screen.findByText('New Request')
    fireEvent.click(await screen.findByRole('button', { name: /Attachments/ }))
    const uploadBtn = await screen.findByRole('button', { name: /Upload/i })
    const file = new File(['data'], 'quote.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.click(uploadBtn)
    await waitFor(() => expect(createDraft).toHaveBeenCalledOnce())
    await waitFor(() => expect(uploadAttachment).toHaveBeenCalledWith('new-1', file))
  })
})

describe('WizardPage — attachments on an existing draft', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRequest).mockResolvedValue(makeRequest('DRAFT'))
  })

  it('uploads to the existing request without creating a new draft', async () => {
    renderAt('/requests/req-1/edit')
    await screen.findByText('Request CX000042')
    fireEvent.click(await screen.findByRole('button', { name: /Attachments/ }))
    const uploadBtn = await screen.findByRole('button', { name: /Upload/i })
    const file = new File(['data'], 'quote.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    fireEvent.click(uploadBtn)
    await waitFor(() => expect(uploadAttachment).toHaveBeenCalledWith('req-1', file))
    expect(createDraft).not.toHaveBeenCalled()
  })
})
