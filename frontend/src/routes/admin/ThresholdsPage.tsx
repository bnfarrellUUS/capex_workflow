import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listThresholds, putThresholds, type Threshold } from '../../api/thresholds'
import { listUsers } from '../../api/users'
import { ApiError } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { TransferList } from '../../components/ui/TransferList'
import { BrandCard } from '../../components/ui/BrandCard'

const LABELS: Record<number, string> = {
  1: 'Level 1 (Manager)',
  2: 'Level 2 (VP/Director)',
  3: 'Level 3 (CFO/CEO)',
}

export default function ThresholdsPage() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['thresholds'], queryFn: listThresholds })
  const { data: users = [] } = useQuery({ queryKey: ['users'], queryFn: listUsers })
  const approvers = users.filter((u) => u.roles.includes('APPROVER'))
  const [rows, setRows] = useState<Threshold[]>([])
  const [saved, setSaved] = useState(false)

  useEffect(() => { if (data) setRows(data) }, [data])

  const mutation = useMutation({
    mutationFn: () => putThresholds(rows),
    onSuccess: (updated) => { qc.setQueryData(['thresholds'], updated); setSaved(true) },
  })
  const error = mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? 'Failed.' : null

  function setRow(level: number, patch: Partial<Threshold>) {
    setRows((cur) => cur.map((r) => (r.level === level ? { ...r, ...patch } : r)))
    setSaved(false)
  }

  return (
    <div className="max-w-3xl">
      <BrandCard title="Approval Thresholds" mark="check"
        subtitle='Approval goes up to the highest level whose cap the request exceeds — leave the top max empty for "no limit"'>
      <div className="space-y-4">
        {rows.map((r) => (
          <div key={r.level} className="rounded-xl border border-border bg-surface p-4 shadow-sm">
            <div className="mb-2 font-medium text-fg">{LABELS[r.level]}</div>
            <div className="space-y-3">
              <div className="max-w-xs space-y-1">
                <label className="text-xs text-muted">Max amount ($)</label>
                <Input type="number" value={r.max_amount ?? ''}
                  placeholder={r.level === 3 ? 'No limit' : ''}
                  onChange={(e) => setRow(r.level, { max_amount: e.target.value === '' ? null : e.target.value })} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted">
                  Approvers {r.level === 1 ? '(set per division)' : '(any one may approve)'}
                </label>
                {r.level === 1 ? (
                  <p className="text-sm text-muted">Level-1 approvers are configured on each division.</p>
                ) : (
                  <TransferList
                    options={approvers.map((u) => ({ id: u.id, label: `${u.name} (${u.username})` }))}
                    selected={r.approver_ids}
                    onChange={(ids) => setRow(r.level, { approver_ids: ids })}
                  />
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
      {error && <p className="mt-4 text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
      {saved && <p className="mt-4 text-sm text-emerald-600 dark:text-emerald-400">Saved.</p>}
      <Button className="mt-4" disabled={mutation.isPending} onClick={() => mutation.mutate()}>Save thresholds</Button>
      </BrandCard>
    </div>
  )
}
