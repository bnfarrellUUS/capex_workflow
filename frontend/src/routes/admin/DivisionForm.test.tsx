// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DivisionForm } from './DivisionForm'
import type { Region } from '../../api/regions'

const regions: Region[] = [
  { id: 'r1', name: 'North', active: true, vp_approver_ids: [] },
  { id: 'r2', name: 'South', active: true, vp_approver_ids: [] },
]

/** Finds the input/select rendered as the sibling of a `<label>` with this text. */
function fieldByLabel(text: string): HTMLInputElement | HTMLSelectElement {
  const label = screen.getByText(text)
  const field = label.parentElement?.querySelector('input, select')
  if (!field) throw new Error(`No field found for label "${text}"`)
  return field as HTMLInputElement | HTMLSelectElement
}

describe('DivisionForm', () => {
  it('shows a required Region combobox with a disabled placeholder option', () => {
    render(
      <DivisionForm approvers={[]} regions={regions} pending={false} error={null} onSubmit={() => {}} />,
    )
    const select = fieldByLabel('Region')
    expect(select.tagName).toBe('SELECT')
    expect(select).toBeRequired()
    const placeholder = screen.getByRole('option', { name: /Select a region/i }) as HTMLOptionElement
    expect(placeholder).toBeDisabled()
    expect(placeholder.value).toBe('')
  })

  it('submits the selected region_id', () => {
    const onSubmit = vi.fn()
    render(
      <DivisionForm approvers={[]} regions={regions} pending={false} error={null} onSubmit={onSubmit} />,
    )
    fireEvent.change(fieldByLabel('Division number'), { target: { value: '10' } })
    fireEvent.change(fieldByLabel('Name'), { target: { value: 'Midwest' } })
    fireEvent.change(fieldByLabel('Region'), { target: { value: 'r2' } })
    fireEvent.click(screen.getByRole('button', { name: /Create division/i }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ region_id: 'r2', number: '10', name: 'Midwest' }),
    )
  })
})
