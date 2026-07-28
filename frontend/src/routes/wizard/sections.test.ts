import { describe, it, expect } from 'vitest'
import { ALL_SECTIONS, visibleSections, isSectionVisible, clampStep } from './sections'

describe('visibleSections', () => {
  it('shows all seven steps when nothing is hidden', () => {
    expect(visibleSections([]).map((s) => s.label)).toEqual([
      'Basic Info', 'Description', 'Effect on Ops', 'Asset Details',
      'Economic', 'Attachments', 'Review',
    ])
  })

  it('renumbers the remaining steps consecutively when Economic is hidden', () => {
    const visible = visibleSections(['economic'])
    expect(visible.map((s) => s.label)).toEqual([
      'Basic Info', 'Description', 'Effect on Ops', 'Asset Details', 'Attachments', 'Review',
    ])
    // Step number is the 1-based position in the visible list.
    expect(visible.findIndex((s) => s.key === 'attachments') + 1).toBe(5)
    expect(visible.findIndex((s) => s.key === 'review') + 1).toBe(6)
  })

  it('renumbers with several sections hidden', () => {
    const visible = visibleSections(['description', 'effect_on_ops', 'economic'])
    expect(visible.map((s) => s.label)).toEqual([
      'Basic Info', 'Asset Details', 'Attachments', 'Review',
    ])
    expect(visible.findIndex((s) => s.key === 'review') + 1).toBe(4)
  })

  it('never hides Basic Info or Review, even if asked to', () => {
    const visible = visibleSections(['basic_info', 'review'])
    expect(visible.map((s) => s.key)).toEqual(ALL_SECTIONS.map((s) => s.key))
  })

  it('ignores unknown keys', () => {
    expect(visibleSections(['nonsense']).length).toBe(ALL_SECTIONS.length)
  })
})

describe('isSectionVisible', () => {
  it('reports a hidden section as not visible', () => {
    expect(isSectionVisible('economic', ['economic'])).toBe(false)
    expect(isSectionVisible('economic', [])).toBe(true)
  })

  it('reports always-visible sections as visible regardless', () => {
    expect(isSectionVisible('basic_info', ['basic_info'])).toBe(true)
    expect(isSectionVisible('review', ['review'])).toBe(true)
  })
})

describe('clampStep', () => {
  it('keeps an in-range step untouched', () => {
    expect(clampStep(2, 6)).toBe(2)
  })

  it('pulls a step past the end back to the last visible step', () => {
    expect(clampStep(6, 6)).toBe(5)
    expect(clampStep(99, 4)).toBe(3)
  })

  it('floors a negative or bad step at zero', () => {
    expect(clampStep(-1, 6)).toBe(0)
    expect(clampStep(NaN, 6)).toBe(0)
  })
})
