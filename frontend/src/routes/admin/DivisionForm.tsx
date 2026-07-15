import { useState } from 'react'
import type { Division, DivisionInput } from '../../api/divisions'
import type { AdminUser } from '../../api/users'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { TransferList } from '../../components/ui/TransferList'

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
  const [l1Ids, setL1Ids] = useState<string[]>(division?.l1_approver_ids ?? [])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    onSubmit({ number, name, active, l1_approver_ids: l1Ids })
  }

  return (
    <form onSubmit={submit} className="max-w-3xl space-y-4">
      <div className="max-w-lg space-y-1">
        <label className="text-sm font-medium">Division number</label>
        <Input value={number} onChange={(e) => setNumber(e.target.value)} required />
      </div>
      <div className="max-w-lg space-y-1">
        <label className="text-sm font-medium">Name</label>
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Level-1 approvers (any one may approve)</label>
        <TransferList
          options={approvers.map((u) => ({ id: u.id, label: `${u.name} (${u.email})` }))}
          selected={l1Ids}
          onChange={setL1Ids}
        />
      </div>
      {division && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active
        </label>
      )}
      {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
      <Button type="submit" disabled={pending}>{division ? 'Save changes' : 'Create division'}</Button>
    </form>
  )
}
