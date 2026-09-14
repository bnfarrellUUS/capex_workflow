// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import WizardPage from './WizardPage'
import type { CapexRequestData } from '../api/requests'
import { ApiError } from '../api/client'
import { readOpenRequests, setOpenRequestStep, touchOpenRequest } from '../openRequests'

vi.mock('../api/requests', () => ({
  getRequest: vi.fn(),
  createDraft: vi.fn(() => Promise.resolve({ id: 'new-1' })),
  updateDraft: vi.fn(() => Promise.resolve({})),
  submitRequest: vi.fn(() => Promise.resolve({})),
  resubmitRequest: vi.fn(() => Promise.resolve({})),
  // No default value: the real endpoint returns the full updated request, and
  // that value lands in the query cache -- each uploading test supplies one.
  uploadAttachment: vi.fn(),
  deleteAttachment: vi.fn(() => Promise.resolve({})),
  attachmentUrl: (id: string, attId: string) => `/api/requests/${id}/attachments/${attId}`,
}))
vi.mock('../api/divisions', () => ({
  listDivisions: vi.fn(() => Promise.resolve([])),
}))
vi.mock('../auth/useMe', () => ({
  useMe: () => ({ data: { id: 'me', name: 'Me', roles: ['REQUESTOR'], division_id: 'div-1' } }),
}))
vi.mock('../api/requestSections', () => ({
  getHiddenSections: vi.fn(() => Promise.resolve([] as string[])),
  saveHiddenSections: vi.fn(() => Promise.resolve([] as string[])),
}))

import { getRequest, createDraft, updateDraft, submitRequest, resubmitRequest, uploadAttachment } from '../api/requests'
import { getHiddenSections } from '../api/requestSections'

function makeRequest(status: string): CapexRequestData {
  return {
    id: 'req-1', number: 'CX000042', status,
    division_id: 'div-1', request_date: '2026-07-13', description: 'Forklift',
    budgeted: false, budget_amount: null,
    replacement: false, health_safety: false, revenue_generating: false,
    environmental: false, competitive_bids: false, lease_recommended: false,
    justification: '', effect_on_operations: '',
    asset_life: null, irr_after_tax: null, first_year_ebit: null,
    annual_savings: null, payback_years: null, npv_savings: null,
    cost_autos_trucks: null, cost_machinery: null, cost_improvements: null,
    cost_furniture: null, cost_it_computer: null, cost_misc: null,
    asset_number: null, gl_account: null, useful_life_years: null, useful_life_months: null, in_service_date: null,
    total_cost: '30000', requestor_id: 'me', assignee_id: null,
    requestor_name: 'Me', assignee_name: null,
    current_approver_ids: [], current_approver_names: [], division_name: '10 — Ops',
    finance_completed: false,
    equipment_items: [{ units: 1, condition: 'NEW', type: 'Lift', make: 'X', model: 'Y', cost: '30000' }],
    actions: [], comments: [], attachments: [],
  }
}

function renderAt(path: string, extra?: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        {extra}
        <Routes>
          <Route path="/requests/new" element={<WizardPage />} />
          <Route path="/requests/:id/edit" element={<WizardPage />} />
          <Route path="/requests/:id" element={<div>Detail</div>} />
          <Route path="/requests" element={<div>List</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function Switcher({ to }: { to: string }) {
  const navigate = useNavigate()
  return <button type="button" onClick={() => navigate(to)}>switch</button>
}

beforeEach(() => {
  localStorage.clear()
})

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
    // The real endpoint returns the full updated request (like getRequest),
    // not {} -- an honest mock here is what the reseed-on-id-change effect
    // (WizardPage.tsx) actually receives once the redirect lands on /new-1/edit.
    vi.mocked(uploadAttachment).mockResolvedValueOnce({
      ...makeRequest('DRAFT'), id: 'new-1',
      attachments: [{ id: 'att-1', filename: 'quote.pdf', content_type: 'application/pdf', size: 3 }],
    })
    renderAt('/requests/new')
    await screen.findByText('New Request')
    fireEvent.click(await screen.findByRole('button', { name: /Attachments/ }))
    await screen.findByRole('button', { name: /Attach file/i })
    const file = new File(['data'], 'quote.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(createDraft).toHaveBeenCalledOnce())
    await waitFor(() => expect(uploadAttachment).toHaveBeenCalledWith('new-1', file))
  })
})

describe('WizardPage — admin-hidden sections', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRequest).mockResolvedValue(makeRequest('DRAFT'))
    vi.mocked(getHiddenSections).mockResolvedValue([])
  })

  it('shows all seven numbered steps when nothing is hidden', async () => {
    renderAt('/requests/req-1/edit')
    expect((await screen.findByRole('button', { name: /Economic/ })).textContent).toMatch(/^5Economic/)
    expect(screen.getByRole('button', { name: /Attachments/ }).textContent).toMatch(/^6Attachments/)
    expect(screen.getByRole('button', { name: /Review/ }).textContent).toMatch(/^7Review/)
  })

  it('drops a hidden step from the stepper and renumbers the rest', async () => {
    vi.mocked(getHiddenSections).mockResolvedValue(['economic'])
    renderAt('/requests/req-1/edit')
    expect((await screen.findByRole('button', { name: /Attachments/ })).textContent).toMatch(/^5Attachments/)
    expect(screen.getByRole('button', { name: /Review/ }).textContent).toMatch(/^6Review/)
    expect(screen.queryByRole('button', { name: /Economic/ })).toBeNull()
  })

  it('skips the hidden step when advancing with Next', async () => {
    vi.mocked(getHiddenSections).mockResolvedValue(['economic'])
    renderAt('/requests/req-1/edit')
    fireEvent.click(await screen.findByRole('button', { name: /Asset Details/ }))
    fireEvent.click(await screen.findByRole('button', { name: /^Next$/ }))
    // Next from Asset Details lands on Attachments, not the hidden Economic step.
    await screen.findByRole('button', { name: /Attach file/i })
    expect(screen.queryByLabelText(/IRR after tax/)).toBeNull()
  })

  it('omits the Next button on the last visible step', async () => {
    vi.mocked(getHiddenSections).mockResolvedValue(['economic', 'attachments'])
    renderAt('/requests/req-1/edit')
    fireEvent.click(await screen.findByRole('button', { name: /Review/ }))
    await screen.findByRole('button', { name: /for approval/i })
    expect(screen.queryByRole('button', { name: /^Next$/ })).toBeNull()
  })

  it('leaves the hidden section out of the Review summary', async () => {
    vi.mocked(getHiddenSections).mockResolvedValue(['asset_details'])
    renderAt('/requests/req-1/edit')
    fireEvent.click(await screen.findByRole('button', { name: /Review/ }))
    await screen.findByRole('button', { name: /for approval/i })
    expect(screen.queryByText(/Asset line items/)).toBeNull()
    expect(screen.queryByText(/Total cost/)).toBeNull()
  })
})

describe('WizardPage — budget amount', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRequest).mockResolvedValue(makeRequest('DRAFT'))
  })

  const amountField = () => screen.queryByPlaceholderText('$0.00')

  async function checkBudgeted() {
    await screen.findByText('Request CX000042')
    fireEvent.click(screen.getByLabelText('Budgeted'))
  }

  it('hides the amount field until Budgeted is checked', async () => {
    renderAt('/requests/req-1/edit')
    await screen.findByText('Request CX000042')
    expect(amountField()).toBeNull()
    fireEvent.click(screen.getByLabelText('Budgeted'))
    expect(amountField()).not.toBeNull()
  })

  it('hides the field again when Budgeted is unchecked', async () => {
    renderAt('/requests/req-1/edit')
    await checkBudgeted()
    fireEvent.click(screen.getByLabelText('Budgeted'))
    expect(amountField()).toBeNull()
  })

  it('blocks Next until an amount is entered', async () => {
    renderAt('/requests/req-1/edit')
    await checkBudgeted()
    fireEvent.click(screen.getByRole('button', { name: /^Next$/ }))
    await screen.findByText('Enter the budgeted amount.')
    // Leaving the step would have auto-saved the draft; it never happened.
    await new Promise((r) => setTimeout(r, 0))
    expect(updateDraft).not.toHaveBeenCalled()
  })

  it('rejects a zero amount', async () => {
    renderAt('/requests/req-1/edit')
    await checkBudgeted()
    fireEvent.change(amountField()!, { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: /^Next$/ }))
    await screen.findByText('Enter a valid dollar amount.')
    expect(updateDraft).not.toHaveBeenCalled()
  })

  it('advances once a valid amount is entered, stripping $ and commas', async () => {
    renderAt('/requests/req-1/edit')
    await checkBudgeted()
    fireEvent.change(amountField()!, { target: { value: '$45,000' } })
    fireEvent.click(screen.getByRole('button', { name: /^Next$/ }))
    await waitFor(() => expect(updateDraft).toHaveBeenCalledWith(
      'req-1', expect.objectContaining({ budgeted: true, budget_amount: '45000' })))
  })

  it('still saves a draft with the amount blank', async () => {
    renderAt('/requests/req-1/edit')
    await checkBudgeted()
    fireEvent.click(screen.getByRole('button', { name: /Save Draft/i }))
    await waitFor(() => expect(updateDraft).toHaveBeenCalledWith(
      'req-1', expect.objectContaining({ budgeted: true, budget_amount: null })))
  })

  it('sends a null amount when Budgeted is off', async () => {
    renderAt('/requests/req-1/edit')
    await checkBudgeted()
    fireEvent.change(amountField()!, { target: { value: '45000' } })
    fireEvent.click(screen.getByLabelText('Budgeted'))
    fireEvent.click(screen.getByRole('button', { name: /Save Draft/i }))
    await waitFor(() => expect(updateDraft).toHaveBeenCalledWith(
      'req-1', expect.objectContaining({ budgeted: false, budget_amount: null })))
  })
})

describe('WizardPage — attachments on an existing draft', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRequest).mockResolvedValue(makeRequest('DRAFT'))
  })

  it('uploads to the existing request without creating a new draft', async () => {
    vi.mocked(uploadAttachment).mockResolvedValueOnce({
      ...makeRequest('DRAFT'),
      attachments: [{ id: 'att-1', filename: 'quote.pdf', content_type: 'application/pdf', size: 3 }],
    })
    renderAt('/requests/req-1/edit')
    await screen.findByText('Request CX000042')
    fireEvent.click(await screen.findByRole('button', { name: /Attachments/ }))
    await screen.findByRole('button', { name: /Attach file/i })
    const file = new File(['data'], 'quote.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => expect(uploadAttachment).toHaveBeenCalledWith('req-1', file))
    expect(createDraft).not.toHaveBeenCalled()
  })
})

describe('WizardPage and the open-request set', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRequest).mockResolvedValue(makeRequest('DRAFT'))
  })

  const currentStep = () =>
    screen.getAllByRole('button', { current: 'step' })[0]

  it('opens an edit tab for the request it loaded', async () => {
    renderAt('/requests/req-1/edit')
    await screen.findByText('Request CX000042')

    expect(readOpenRequests('me')).toMatchObject([
      { id: 'req-1', number: 'CX000042', title: 'Forklift', mode: 'edit', step: 0 },
    ])
  })

  it('reopens the request on the step it was left on', async () => {
    touchOpenRequest('me', { id: 'req-1', number: 'CX000042', title: 'Forklift', mode: 'edit' })
    setOpenRequestStep('me', 'req-1', 2)

    renderAt('/requests/req-1/edit')
    await screen.findByText('Request CX000042')

    expect(currentStep()).toHaveTextContent('Effect on Ops')
  })

  it('remembers the step when you move through the wizard', async () => {
    renderAt('/requests/req-1/edit')
    await screen.findByText('Request CX000042')

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(readOpenRequests('me')[0].step).toBe(1))
    expect(currentStep()).toHaveTextContent('Description')
  })

  it('keeps each request on its own step when you switch between tabs', async () => {
    touchOpenRequest('me', { id: 'a', number: 'CX000001', title: 'One', mode: 'edit' })
    setOpenRequestStep('me', 'a', 2)
    touchOpenRequest('me', { id: 'b', number: 'CX000002', title: 'Two', mode: 'edit' })
    vi.mocked(getRequest).mockImplementation(async (id: string) => ({
      ...makeRequest('DRAFT'), id,
      number: id === 'a' ? 'CX000001' : 'CX000002',
      description: id === 'a' ? 'One' : 'Two',
    }))

    renderAt('/requests/a/edit', <Switcher to="/requests/b/edit" />)
    await screen.findByText('Request CX000001')
    expect(currentStep()).toHaveTextContent('Effect on Ops')

    // Same route component, changed param -- local step state would carry
    // request a's step across and land b on Effect on Ops, and a form seeded
    // once for a would show (and save!) a's fields as b's.
    fireEvent.click(screen.getByRole('button', { name: 'switch' }))

    await screen.findByText('Request CX000002')
    expect(currentStep()).toHaveTextContent('Basic Info')
    expect(await screen.findByDisplayValue('Two')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('One')).toBeNull()
  })

  it('shows Loading, not request A’s form, while request B is still loading after a tab switch', async () => {
    touchOpenRequest('me', { id: 'a', number: 'CX000001', title: 'One', mode: 'edit' })
    touchOpenRequest('me', { id: 'b', number: 'CX000002', title: 'Two', mode: 'edit' })
    vi.mocked(getRequest).mockImplementation((id: string) =>
      id === 'a'
        ? Promise.resolve({ ...makeRequest('DRAFT'), id: 'a', number: 'CX000001', description: 'One' })
        : new Promise<CapexRequestData>(() => {}))

    renderAt('/requests/a/edit', <Switcher to="/requests/b/edit" />)
    await screen.findByDisplayValue('One')

    fireEvent.click(screen.getByRole('button', { name: 'switch' }))

    // The form still holds a's values, but the URL says b: showing it here
    // would let Save Draft / Next / Submit write a's fields into b.
    expect(await screen.findByText('Loading…')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('One')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Save Draft' })).toBeNull()
    expect(updateDraft).not.toHaveBeenCalled()
  })

  it('drops one request’s “Saved.” when you switch to another tab', async () => {
    touchOpenRequest('me', { id: 'a', number: 'CX000001', title: 'One', mode: 'edit' })
    touchOpenRequest('me', { id: 'b', number: 'CX000002', title: 'Two', mode: 'edit' })
    vi.mocked(getRequest).mockImplementation(async (id: string) => ({
      ...makeRequest('DRAFT'), id,
      number: id === 'a' ? 'CX000001' : 'CX000002',
      description: id === 'a' ? 'One' : 'Two',
    }))

    renderAt('/requests/a/edit', <Switcher to="/requests/b/edit" />)
    await screen.findByText('Request CX000001')
    fireEvent.click(screen.getByRole('button', { name: 'Save Draft' }))
    await screen.findByText('Saved.')

    fireEvent.click(screen.getByRole('button', { name: 'switch' }))

    await screen.findByText('Request CX000002')
    expect(screen.queryByText('Saved.')).toBeNull()
  })

  it('carries a new request’s step into its tab across the first-save redirect', async () => {
    vi.mocked(getRequest).mockResolvedValue({ ...makeRequest('DRAFT'), id: 'new-1' })
    renderAt('/requests/new')
    await screen.findByText('New Request')

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(currentStep()).toHaveTextContent('Description')
    fireEvent.click(screen.getByRole('button', { name: 'Save Draft' }))

    await waitFor(() => expect(readOpenRequests('me')).toMatchObject([{ id: 'new-1', step: 1 }]))
    expect(currentStep()).toHaveTextContent('Description')
  })

  it('offers to close the tab when the request cannot be loaded', async () => {
    touchOpenRequest('me', { id: 'req-1', number: 'CX000042', title: 'Gone', mode: 'edit' })
    vi.mocked(getRequest).mockRejectedValue(new ApiError(404, 'Request not found.'))

    renderAt('/requests/req-1/edit')

    // Without this the route shows "Loading…" forever -- and a stored tab is
    // exactly how a request that no longer exists gets opened.
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not be loaded/i)
    fireEvent.click(screen.getByRole('button', { name: /Close this tab/ }))

    expect(readOpenRequests('me')).toEqual([])
    expect(await screen.findByText('List')).toBeInTheDocument()
  })
})
