import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getHiddenSections, saveHiddenSections } from '../../api/requestSections'
import { ALL_SECTIONS, visibleSections } from '../wizard/sections'
import { ApiError } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { BrandCard } from '../../components/ui/BrandCard'

// Extra context shown under a section whose absence changes how requests behave.
const NOTES: Record<string, string> = {
  asset_details: 'Hiding this leaves requests with no line items, so the total is $0 — '
    + 'and since approval levels derive from the total, every request routes at Level 1 only.',
}

export default function RequestSectionsPage() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['request-sections'], queryFn: getHiddenSections })
  // The saved config is the source of truth until the admin touches a toggle;
  // `edits` then holds the pending selection. Deriving rather than mirroring the
  // query into state means a refetch can't overwrite unsaved changes.
  const [edits, setEdits] = useState<string[] | null>(null)
  const [saved, setSaved] = useState(false)
  const hidden = edits ?? data ?? []

  const mutation = useMutation({
    mutationFn: () => saveHiddenSections(hidden),
    onSuccess: (updated) => {
      qc.setQueryData(['request-sections'], updated)
      setEdits(null)
      setSaved(true)
    },
  })
  const error = mutation.error instanceof ApiError ? mutation.error.message
    : mutation.error ? 'Failed.' : null

  // Numbers come from the same helper the wizard uses, so the preview matches.
  const visible = visibleSections(hidden)
  const stepNumber = (key: string) => {
    const i = visible.findIndex((s) => s.key === key)
    return i === -1 ? '—' : String(i + 1)
  }

  function toggle(key: string) {
    setEdits(hidden.includes(key) ? hidden.filter((k) => k !== key) : [...hidden, key])
    setSaved(false)
  }

  // Wait for the saved config so the toggles never show everything as visible
  // for a beat before the real setting lands.
  if (!data) return <p className="text-sm text-muted">Loading…</p>

  return (
    <div className="max-w-3xl">
      <BrandCard title="Request Sections" mark="newRequest"
        subtitle="Choose which steps requestors see in the New Request wizard — the remaining steps renumber automatically">
        <ul className="space-y-2">
          {ALL_SECTIONS.map(({ key, label, always }) => {
            const shown = !hidden.includes(key) || always
            return (
              <li key={key} data-section-row
                className="flex items-start gap-4 rounded-xl border border-border bg-surface p-4 shadow-sm">
                <span data-step-number
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                    shown ? 'bg-accent/15 text-accent' : 'border border-border bg-surface-2 text-muted'
                  }`}>
                  {stepNumber(key)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className={`font-medium ${shown ? 'text-fg' : 'text-muted'}`}>{label}</div>
                  {NOTES[key] && <p className="mt-1 text-xs text-muted">{NOTES[key]}</p>}
                </div>
                {always ? (
                  <span className="shrink-0 text-xs text-muted">(always)</span>
                ) : (
                  <label className="flex shrink-0 items-center gap-2 text-sm">
                    <input type="checkbox" aria-label={label} checked={shown}
                      onChange={() => toggle(key)} />
                    <span className={shown ? 'text-fg' : 'text-muted'}>{shown ? 'Shown' : 'Hidden'}</span>
                  </label>
                )}
              </li>
            )
          })}
        </ul>
        {error && <p className="mt-4 text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
        {saved && <p className="mt-4 text-sm text-emerald-600 dark:text-emerald-400">Saved.</p>}
        <Button className="mt-4" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
          Save sections
        </Button>
      </BrandCard>
    </div>
  )
}
