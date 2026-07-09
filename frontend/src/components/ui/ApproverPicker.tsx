export function ApproverPicker({
  options,
  selected,
  onChange,
  disabled = false,
}: {
  options: { id: string; label: string }[]
  selected: string[]
  onChange: (ids: string[]) => void
  disabled?: boolean
}) {
  if (options.length === 0) return <p className="text-sm text-muted">No approvers available.</p>
  const toggle = (id: string) =>
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  return (
    <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border border-border bg-surface p-2">
      {options.map((o) => (
        <label key={o.id} className="flex items-center gap-2 text-sm text-fg">
          <input
            type="checkbox"
            checked={selected.includes(o.id)}
            disabled={disabled}
            onChange={() => toggle(o.id)}
          />
          {o.label}
        </label>
      ))}
    </div>
  )
}
