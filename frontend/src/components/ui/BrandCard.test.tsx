// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { BrandCard, type PageMark } from './BrandCard'

const MARKS: PageMark[] = [
  'dashboard', 'newRequest', 'requests', 'users',
  'divisions', 'thresholds', 'emailTemplates', 'profile',
]

describe('BrandCard', () => {
  it.each(MARKS)('renders the %s page mark icon and the title', (mark) => {
    const { container, getByText } = render(
      <BrandCard title="Some Page" mark={mark}>body</BrandCard>,
    )
    expect(getByText('Some Page')).toBeTruthy()
    expect(container.querySelector('svg')).not.toBeNull()
  })
})
