// The wizard's steps as a keyed registry rather than positional indexes, so an
// admin can hide a section and the rest renumber consecutively on their own.
// Adding a step means adding an entry here (and its body in WizardPage).

export type SectionKey =
  | 'basic_info' | 'description' | 'effect_on_ops' | 'asset_details'
  | 'economic' | 'attachments' | 'review'

export interface Section {
  key: SectionKey
  label: string
  /** Sub-label on the step card, so a step explains itself without training. */
  hint: string
  /** Basic Info carries the Division that drives L1 routing; Review carries Submit. */
  always?: boolean
}

export const ALL_SECTIONS: Section[] = [
  { key: 'basic_info', label: 'Basic Info', hint: 'division & flags', always: true },
  { key: 'description', label: 'Description', hint: 'justification' },
  { key: 'effect_on_ops', label: 'Effect on Ops', hint: 'operations impact' },
  { key: 'asset_details', label: 'Asset Details', hint: 'equipment line items' },
  { key: 'economic', label: 'Economic', hint: 'IRR, payback, NPV' },
  { key: 'attachments', label: 'Attachments', hint: 'quotes, drawings' },
  { key: 'review', label: 'Review', hint: 'summary & submit', always: true },
]

export function isSectionVisible(key: SectionKey, hidden: string[]): boolean {
  const section = ALL_SECTIONS.find((s) => s.key === key)
  return !!section && (section.always === true || !hidden.includes(key))
}

export function visibleSections(hidden: string[]): Section[] {
  return ALL_SECTIONS.filter((s) => s.always || !hidden.includes(s.key))
}

/** Keep a step index inside the visible list — the config can change mid-session. */
export function clampStep(step: number, count: number): number {
  if (!Number.isFinite(step) || step < 0) return 0
  return Math.min(step, count - 1)
}
