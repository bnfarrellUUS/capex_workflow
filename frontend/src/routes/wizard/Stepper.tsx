import { CheckIcon } from '../../components/ActionIcons'
import type { Section } from './sections'

/**
 * Wide equal-flex step cards, rendered into BrandCard's subheader slot.
 * Ported from SCORE's wizard stepper.
 *
 * Each card carries a badge, a label and a hint. Numbers come from position in
 * the visible list, so hiding a section renumbers the rest for free. The badge
 * colour tracks progress: green check for steps already passed, accent for the
 * current step, grey for steps not yet reached.
 */
export function Stepper({
  sections,
  current,
  onSelect,
  disabled = false,
}: {
  sections: Section[]
  current: number
  onSelect: (index: number) => void
  disabled?: boolean
}) {
  return (
    <div className="flex gap-2 border-b border-border bg-surface-2 px-4 py-3">
      {sections.map((section, i) => {
        const done = i < current
        const active = i === current
        return (
          <button
            key={section.key}
            type="button"
            disabled={disabled}
            onClick={() => { if (!active) onSelect(i) }}
            aria-current={active ? 'step' : undefined}
            className={`min-w-0 flex-1 rounded-lg border px-3 py-2 text-left transition disabled:opacity-60 ${
              active
                ? 'border-accent bg-surface text-fg ring-2 ring-accent/20'
                : 'border-border bg-surface text-muted hover:border-accent/60'
            }`}
          >
            <span className="flex items-center gap-2">
              <span
                className={`inline-flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                  done
                    ? 'bg-emerald-600 text-white'
                    : active
                      ? 'bg-accent text-accent-fg'
                      : 'bg-border text-muted'
                }`}
              >
                {done ? <CheckIcon size={11} /> : i + 1}
              </span>
              <span className="min-w-0 truncate text-[13px] font-semibold">{section.label}</span>
            </span>
            <span className="mt-0.5 block truncate text-[11px] text-muted">{section.hint}</span>
          </button>
        )
      })}
    </div>
  )
}
