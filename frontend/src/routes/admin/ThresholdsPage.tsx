import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listThresholds, putThresholds, type Threshold } from '../../api/thresholds'
import { listUsers } from '../../api/users'
import { ApiError } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'

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
    <div className="max-w-2xl">
      <h1 className="mb-4 text-2xl font-semibold text-fg">Approval Thresholds</h1>
      <p className="mb-4 text-sm text-muted">
        A request needs approval up to the highest level whose cap it exceeds. Leave the top level's max empty for "no limit".
      </p>
      <div className="space-y-4">
        {rows.map((r) => (
          <div key={r.level} className="rounded-xl border border-border bg-surface p-4 shadow-sm">
            <div className="mb-2 font-medium text-fg">{LABELS[r.level]}</div>
            <div className="flex gap-4">
              <div className="flex-1 space-y-1">
                <label className="text-xs text-muted">Max amount ($)</label>
                <Input type="number" value={r.max_amount ?? ''}
                  placeholder={r.level === 3 ? 'No limit' : ''}
                  onChange={(e) => setRow(r.level, { max_amount: e.target.value === '' ? null : e.target.value })} />
              </div>
              <div className="flex-1 space-y-1">
                <label className="text-xs text-muted">Approver {r.level === 1 ? '(per division)' : ''}</label>
                <Select value={r.approver_id ?? ''} disabled={r.level === 1}
                  onChange={(e) => setRow(r.level, { approver_id: e.target.value || null })}>
                  <option value="">{r.level === 1 ? 'Set on each division' : '— None —'}</option>
                  {approvers.map((u) => (
                    <option key={u.id} value={u.id}>{u.name} ({u.username})</option>
                  ))}
                </Select>
              </div>
            </div>
          </div>
        ))}
      </div>
      {error && <p className="mt-4 text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
      {saved && <p className="mt-4 text-sm text-emerald-600 dark:text-emerald-400">Saved.</p>}
      <Button className="mt-4" disabled={mutation.isPending} onClick={() => mutation.mutate()}>Save thresholds</Button>
    </div>
  )
}
