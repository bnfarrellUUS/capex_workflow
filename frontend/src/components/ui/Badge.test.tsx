// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { StatusBadge } from './Badge'

describe('StatusBadge', () => {
  it.each([
    ['DRAFT', 'Draft'],
    ['PENDING_L1', 'Pending L1'],
    ['APPROVED', 'Approved'],
    ['REJECTED', 'Rejected'],
  ])('renders %s with its label and a status icon', (status, label) => {
    const { container } = render(<StatusBadge status={status} />)
    expect(container.textContent).toContain(label)
    expect(container.querySelector('svg')).not.toBeNull()
  })
})
