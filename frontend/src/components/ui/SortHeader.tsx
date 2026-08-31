import { ChevronUp, ChevronDown } from 'lucide-react'

/**
 * Clickable table header cell with sort chevrons — the same look and
 * aria-sort behavior as the Requests list's sortable columns, extracted so
 * the admin tables (Divisions, Regions, Users) can share it.
 */
export function SortHeader({
  label,
  active,
  dir,
  onClick,
}: {
  label: string
  /** Is this the column currently sorted? */
  active: boolean
  dir: 'asc' | 'desc'
  onClick: () => void
}) {
  return (
    <th
      aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : undefined}
      className="py-2 pr-4 font-semibold"
    >
      <button
        onClick={onClick}
        className="group inline-flex items-center gap-1 uppercase tracking-wide hover:text-accent"
      >
        {label}
        {active ? (
          dir === 'asc' ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />
        ) : (
          <ChevronUp className="h-3.5 w-3.5 opacity-0 group-hover:opacity-40" />
        )}
      </button>
    </th>
  )
}
