import { useState } from 'react'
import type { Region, RegionInput } from '../../api/regions'
import type { AdminUser } from '../../api/users'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { TransferList } from '../../components/ui/TransferList'

export function RegionForm({
  approvers, region, pending, error, onSubmit,
}: {
  approvers: AdminUser[]
  region?: Region
  pending: boolean
  error: string | null
  onSubmit: (body: RegionInput) => void
}) {
  const [name, setName] = useState(region?.name ?? '')
  const [active, setActive] = useState(region?.active ?? true)
  const [vpIds, setVpIds] = useState<string[]>(region?.vp_approver_ids ?? [])

  function submit(e: React.FormEvent) {
    e.preventDefault()
    onSubmit({ name, active, vp_approver_ids: vpIds })
  }

  return (
    <form onSubmit={submit} className="max-w-3xl space-y-4">
      <div className="max-w-lg space-y-1">
        <label className="text-sm font-medium">Name</label>
        <Input value={name} onChange={(e) => setName(e.target.value)} required />
      </div>
      <div className="space-y-1">
        <label className="text-sm font-medium">Region VPs — Level-2 approvers (any one may approve)</label>
        <TransferList
          options={approvers.map((u) => ({ id: u.id, label: `${u.name} (${u.email})` }))}
          selected={vpIds}
          onChange={setVpIds}
        />
      </div>
      {region && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active
        </label>
      )}
      {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
      <Button type="submit" disabled={pending}>{region ? 'Save changes' : 'Create region'}</Button>
    </form>
  )
}
