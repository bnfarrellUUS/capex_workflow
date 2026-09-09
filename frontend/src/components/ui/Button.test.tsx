// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Button } from './Button'

describe('Button size', () => {
  it('defaults to the medium padding', () => {
    render(<Button>Go</Button>)
    expect(screen.getByRole('button').className).toContain('px-4 py-2 text-sm')
  })

  it('renders a compact button for size="sm"', () => {
    render(<Button size="sm">Ping</Button>)
    const cls = screen.getByRole('button').className
    expect(cls).toContain('px-3 py-1.5 text-xs')
    expect(cls).not.toContain('px-4')
  })
})
