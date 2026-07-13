// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import EmailTemplateEditor from './EmailTemplateEditor'
import * as apiMod from '../../api/emailTemplates'

vi.mock('../../api/emailTemplates')
vi.mock('../../components/ui/QuillEditor', () => ({ QuillEditor: () => null }))

const TEMPLATES = [
  { type: 'ASSIGNED', name: 'Approval needed', subject: 'S', enabled: true, is_custom: false },
  { type: 'APPROVED', name: 'Approved', subject: 'S', enabled: true, is_custom: false },
  { type: 'REJECTED', name: 'Rejected', subject: 'S', enabled: false, is_custom: false },
  { type: 'FINANCE_READY', name: 'Finance ready', subject: 'S', enabled: true, is_custom: false },
]

function tmpl(type: string, name: string) {
  return {
    type, name, subject: 'S', body_html: '<p>x</p>', enabled: true, is_custom: false,
    default_subject: 'S', default_body_html: '<p>x</p>',
    tokens: [{ token: '{number}', description: 'Request number' }],
    button_label: 'Review & approve',
  }
}

function renderAt(startType = 'ASSIGNED') {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/admin/email-templates/${startType}`]}>
        <Routes><Route path="/admin/email-templates/:type" element={<EmailTemplateEditor />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('EmailTemplateEditor', () => {
  beforeEach(() => {
    vi.mocked(apiMod.listEmailTemplates).mockResolvedValue(TEMPLATES as never)
    vi.mocked(apiMod.getEmailSettings).mockResolvedValue({ mode: 'test', test_recipient: 'tester@uus.com' })
    vi.mocked(apiMod.getEmailTemplate).mockImplementation((type: string) =>
      Promise.resolve(tmpl(type, TEMPLATES.find((t) => t.type === type)!.name) as never))
  })

  it('shows placeholders for the template', async () => {
    renderAt()
    await waitFor(() => expect(screen.getByText('{number}')).toBeInTheDocument())
    fireEvent.click(screen.getByText('{number}'))   // does not throw
    expect(screen.getByText('Request number')).toBeInTheDocument()
    expect(screen.getByText('Review & approve')).toBeInTheDocument()
  })

  it('renders a tab per template with the current one active', async () => {
    renderAt()
    await waitFor(() => expect(screen.getByRole('tab', { name: /Approval needed/ })).toBeInTheDocument())
    expect(screen.getByRole('tab', { name: /Approved/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Rejected/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Finance ready/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Approval needed/ })).toHaveAttribute('aria-selected', 'true')
  })

  it('switches templates when a tab is clicked (no unsaved edits)', async () => {
    renderAt()
    await waitFor(() => expect(screen.getByRole('tab', { name: /Approved/ })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('tab', { name: /Approved/ }))
    await waitFor(() => expect(apiMod.getEmailTemplate).toHaveBeenCalledWith('APPROVED'))
  })

  it('warns before switching when there are unsaved edits and stays if cancelled', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderAt()
    await waitFor(() => expect(screen.getByRole('tab', { name: /Rejected/ })).toBeInTheDocument())
    fireEvent.change(screen.getByDisplayValue('S'), { target: { value: 'edited subject' } })
    fireEvent.click(screen.getByRole('tab', { name: /Rejected/ }))
    expect(confirmSpy).toHaveBeenCalledOnce()
    expect(apiMod.getEmailTemplate).not.toHaveBeenCalledWith('REJECTED')
    confirmSpy.mockRestore()
  })

  it('switches when unsaved edits are confirmed to be discarded', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderAt()
    await waitFor(() => expect(screen.getByRole('tab', { name: /Rejected/ })).toBeInTheDocument())
    fireEvent.change(screen.getByDisplayValue('S'), { target: { value: 'edited subject' } })
    fireEvent.click(screen.getByRole('tab', { name: /Rejected/ }))
    await waitFor(() => expect(apiMod.getEmailTemplate).toHaveBeenCalledWith('REJECTED'))
    confirmSpy.mockRestore()
  })
})
