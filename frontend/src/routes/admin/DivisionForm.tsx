import { useState } from 'react'
import type { Division, DivisionInput } from '../../api/divisions'
import type { AdminUser } from '../../api/users'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'

export function DivisionForm({
  approvers, division, pending, error, onSubmit,
}: {
  approvers: AdminUser[]
  division?: Division
  pending: boolean
  error: string | null
  onSubmit: (body: DivisionInput) => void
}) {
  const [number, setNumber] = useState(division?.number ?? '')
  const [name, setName] = useState(division?.name ?? '')
  const [active, setActive] = useState(division?.active ?? true)
  const [l1, setL1] = useState(division?.l1_approver_id ?? '')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    onSubmit({ number, name, active, l1_approver_id: l1 || null })
  }

  return (
    <form onSubmit={submit} className="max-w-lg space-y-4">
      <div className="space-y-1">
        <label className="text-sm font-medium">Division number</label>
        <Input value={number} onChange={(e) => setNumber(e.target.value)} required />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Name</label>
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Level-1 approver</label>
        <Select value={l1} onChange={(e) => setL1(e.target.value)}>
          <option value="">— None —</option>
          {approvers.map((u) => (
            <option key={u.id} value={u.id}>{u.name} ({u.username})</option>
          ))}
        </Select>
      </div>
      {division && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active
        </label>
      )}
      {error && <p className="text-sm text-red-600" role="alert">{error}</p>}
      <Button type="submit" disabled={pending}>{division ? 'Save changes' : 'Create division'}</Button>
    </form>
  )
}
