import { useState } from 'react'
import { ChevronUp, ChevronDown } from 'lucide-react'
import { Button } from './Button'

/**
 * Dual-listbox (shuttle) picker: choose items from an Available pool into an
 * ordered Selected list, with Add/Remove and ▲▼ reorder. `selected` holds the
 * chosen ids in display order; `onChange` receives the new ordered list.
 */
export function TransferList({
  options,
  selected,
  onChange,
  disabled = false,
  availableLabel = 'Available',
  selectedLabel = 'Selected',
  numbered = true,
}: {
  options: { id: string; label: string }[]
  selected: string[]
  onChange: (ids: string[]) => void
  disabled?: boolean
  availableLabel?: string
  selectedLabel?: string
  numbered?: boolean
}) {
  // Highlighted (single) id within each panel; local UI state only.
  const [availHi, setAvailHi] = useState<string | null>(null)
  const [selHi, setSelHi] = useState<string | null>(null)

  const byId = (id: string) => options.find((o) => o.id === id)
  const availableItems = options.filter((o) => !selected.includes(o.id))
  const selectedItems = selected.map(byId).filter((o): o is { id: string; label: string } => !!o)

  function add(id: string) {
    if (disabled || selected.includes(id)) return
    onChange([...selected, id])
    setAvailHi(null)
  }
  function remove(id: string) {
    if (disabled) return
    onChange(selected.filter((x) => x !== id))
    setSelHi(null)
  }
  function move(dir: -1 | 1) {
    if (disabled || !selHi) return
    const i = selected.indexOf(selHi)
    const j = i + dir
    if (i < 0 || j < 0 || j >= selected.length) return
    const next = [...selected]
    ;[next[i], next[j]] = [next[j], next[i]]
    onChange(next)
  }

  const panel = 'h-48 overflow-y-auto rounded-md border border-border bg-surface'
  const row = 'cursor-pointer px-3 py-1.5 text-sm text-fg'
  const hiRow = 'bg-accent text-accent-fg'

  return (
    <div className="flex items-stretch gap-3">
      {/* Available */}
      <div className="flex-1">
        <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">{availableLabel}</div>
        <ul className={panel}>
          {availableItems.length === 0 ? (
            <li className="px-3 py-1.5 text-sm text-muted">None available.</li>
          ) : (
            availableItems.map((o) => (
              <li
                key={o.id}
                className={`${row} ${availHi === o.id ? hiRow : 'hover:bg-surface-2'}`}
                onClick={() => setAvailHi(o.id)}
                onDoubleClick={() => add(o.id)}
              >
                {o.label}
              </li>
            ))
          )}
        </ul>
      </div>

      {/* Add / Remove */}
      <div className="flex flex-col justify-center gap-2">
        <Button type="button" variant="secondary" disabled={disabled || !availHi} onClick={() => availHi && add(availHi)}>
          Add &raquo;
        </Button>
        <Button type="button" variant="secondary" disabled={disabled || !selHi} onClick={() => selHi && remove(selHi)}>
          &laquo; Remove
        </Button>
      </div>

      {/* Selected */}
      <div className="flex-1">
        <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">{selectedLabel}</div>
        <ul className={panel}>
          {selectedItems.length === 0 ? (
            <li className="px-3 py-1.5 text-sm text-muted">None selected.</li>
          ) : (
            selectedItems.map((o, idx) => (
              <li
                key={o.id}
                className={`${row} flex items-center gap-2 ${selHi === o.id ? hiRow : 'hover:bg-surface-2'}`}
                onClick={() => setSelHi(o.id)}
                onDoubleClick={() => remove(o.id)}
              >
                {numbered && <span className="w-5 shrink-0 tabular-nums opacity-70">{idx + 1}</span>}
                {o.label}
              </li>
            ))
          )}
        </ul>
      </div>

      {/* Reorder */}
      <div className="flex flex-col justify-center gap-2">
        <Button type="button" variant="secondary" className="px-2" aria-label="Move up"
          disabled={disabled || !selHi || selected.indexOf(selHi) <= 0}
          onClick={() => move(-1)}>
          <ChevronUp size={16} />
        </Button>
        <Button type="button" variant="secondary" className="px-2" aria-label="Move down"
          disabled={disabled || !selHi || selected.indexOf(selHi) === selected.length - 1}
          onClick={() => move(1)}>
          <ChevronDown size={16} />
        </Button>
      </div>
    </div>
  )
}
