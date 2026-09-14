// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { Stepper } from './Stepper'
import { visibleSections } from './sections'

const sections = visibleSections([])

test('renders a card per visible section with its label and hint', () => {
  render(<Stepper sections={sections} current={0} onSelect={() => {}} />)
  expect(screen.getByText('Basic Info')).toBeTruthy()
  expect(screen.getByText('division & flags')).toBeTruthy()
  expect(screen.getAllByRole('button')).toHaveLength(sections.length)
})

test('numbers come from position in the visible list, not a hardcoded index', () => {
  const trimmed = visibleSections(['description'])
  render(<Stepper sections={trimmed} current={0} onSelect={() => {}} />)
  // Effect on Ops is step 2 now that Description is hidden.
  expect(screen.getByRole('button', { name: /Effect on Ops/ }).textContent).toContain('2')
})

test('the current step is marked for assistive tech, not by colour alone', () => {
  render(<Stepper sections={sections} current={1} onSelect={() => {}} />)
  expect(screen.getByRole('button', { name: /Description/ }).getAttribute('aria-current')).toBe('step')
})

test('only one step is current at a time', () => {
  render(<Stepper sections={sections} current={2} onSelect={() => {}} />)
  const marked = screen.getAllByRole('button').filter((b) => b.getAttribute('aria-current') === 'step')
  expect(marked).toHaveLength(1)
})

test('steps before the current one show a green check instead of their number', () => {
  render(<Stepper sections={sections} current={2} onSelect={() => {}} />)
  const done = screen.getByRole('button', { name: /Basic Info/ })
  expect(done.textContent).not.toContain('1')
  expect(done.querySelector('.bg-emerald-600 svg')).not.toBeNull()
  // The current step keeps its number in the accent badge …
  const active = screen.getByRole('button', { name: /Effect on Ops/ })
  expect(active.querySelector('.bg-accent')?.textContent).toBe('3')
  // … and steps not yet reached are grey with their number.
  const pending = screen.getByRole('button', { name: /Review/ })
  expect(pending.querySelector('.bg-border')?.textContent).toBe('7')
})

test('clicking a step reports its index', () => {
  const onSelect = vi.fn()
  render(<Stepper sections={sections} current={0} onSelect={onSelect} />)
  screen.getByRole('button', { name: /Effect on Ops/ }).click()
  expect(onSelect).toHaveBeenCalledWith(2)
})

test('disabled blocks every card while a save is in flight', () => {
  render(<Stepper sections={sections} current={0} onSelect={() => {}} disabled />)
  screen.getAllByRole('button').forEach((b) => expect(b).toBeDisabled())
})
