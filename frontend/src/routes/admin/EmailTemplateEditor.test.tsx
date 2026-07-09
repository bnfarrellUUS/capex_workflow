// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import EmailTemplateEditor from './EmailTemplateEditor'
import * as apiMod from '../../api/emailTemplates'

vi.mock('../../api/emailTemplates')
vi.mock('../../components/ui/QuillEditor', () => ({ QuillEditor: () => null }))

function renderAt() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/admin/email-templates/ASSIGNED']}>
        <Routes><Route path="/admin/email-templates/:type" element={<EmailTemplateEditor />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('EmailTemplateEditor', () => {
  it('shows placeholders for the template', async () => {
    vi.mocked(apiMod.getEmailTemplate).mockResolvedValue({
      type: 'ASSIGNED', name: 'Approval needed', subject: 'S', body_html: '<p>x</p>',
      enabled: true, is_custom: false, default_subject: 'S', default_body_html: '<p>x</p>',
      tokens: [{ token: '{number}', description: 'Request number' }],
      button_label: 'Review & approve',
    } as never)
    renderAt()
    await waitFor(() => expect(screen.getByText('{number}')).toBeInTheDocument())
    fireEvent.click(screen.getByText('{number}'))   // does not throw
    expect(screen.getByText('Request number')).toBeInTheDocument()
    // the locked CTA button replica is shown below the editor
    expect(screen.getByText('Review & approve')).toBeInTheDocument()
  })
})
