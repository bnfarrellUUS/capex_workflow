import { useState, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getRequest, approveRequest, rejectRequest, resubmitRequest, completeFinance,
  uploadAttachment, deleteAttachment, attachmentUrl,
  type CapexRequestData,
} from '../api/requests'
import { useMe } from '../auth/useMe'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { BrandCard } from '../components/ui/BrandCard'
import { StatusBadge } from '../components/ui/Badge'

const PIPELINE = ['DRAFT', 'PENDING_L1', 'PENDING_L2', 'PENDING_L3', 'APPROVED']

export default function RequestDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: me } = useMe()
  const { data: req } = useQuery({ queryKey: ['request', id], queryFn: () => getRequest(id) })
  const [comment, setComment] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  async function act(fn: () => Promise<CapexRequestData>) {
    setErr(null)
    setBusy(true)
    try {
      qc.setQueryData(['request', id], await fn())
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : 'Action failed.')
    } finally {
      setBusy(false)
    }
  }

  if (!req || !me) return <p className="text-sm text-muted">Loading…</p>

  const isAssignee = req.status.startsWith('PENDING_') && req.current_approver_ids.includes(me.id)
  const isOwner = req.requestor_id === me.id
  const canEdit = isOwner && (req.status === 'DRAFT' || req.status === 'REJECTED')
  const canResubmit = isOwner && req.status === 'REJECTED'
  const canFinance = me.roles.includes('FINANCE') && req.status === 'APPROVED' && !req.finance_completed
  const hasActions = isAssignee || canEdit || canResubmit || canFinance

  const pipeline = (
    <ol className="flex flex-wrap items-center gap-2 border-b border-border bg-surface-2 px-7 py-3 text-xs">
      {PIPELINE.map((s) => (
        <li key={s} className={`rounded-full px-2.5 py-1 ${s === req.status ? 'bg-accent font-semibold text-accent-fg' : 'bg-surface text-muted'}`}>{s}</li>
      ))}
      {req.status === 'REJECTED' && <li className="rounded-full bg-red-600 px-2.5 py-1 font-semibold text-white">REJECTED</li>}
    </ol>
  )

  return (
    <div className="max-w-3xl space-y-4">
      <BrandCard
        title={`Request ${req.number}`}
        subtitle={req.division_name ?? 'Capital expenditure request'}
        actions={<StatusBadge status={req.status} />}
        subheader={pipeline}
        bodyClassName="space-y-6 px-7 py-6"
      >
      <section className="grid grid-cols-2 gap-2 text-sm">
        <div><span className="font-medium">Requestor:</span> {req.requestor_name}</div>
        <div><span className="font-medium">Division:</span> {req.division_name ?? '—'}</div>
        <div><span className="font-medium">Awaiting:</span> {req.current_approver_names.length ? req.current_approver_names.join(', ') : (req.assignee_name ?? '—')}</div>
        <div><span className="font-medium">Total cost:</span> ${Number(req.total_cost ?? 0).toLocaleString()}</div>
        <div className="col-span-2"><span className="font-medium">Description:</span> {req.description || '—'}</div>
      </section>

      <section>
        <h2 className="mb-1 font-semibold text-fg">Equipment</h2>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
              <th className="py-1">Units</th><th>Type</th><th>Make</th><th>Model</th><th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {req.equipment_items.map((i, idx) => (
              <tr key={idx} className="border-b border-border">
                <td className="py-1">{i.units}</td><td>{i.type}</td><td>{i.make}</td><td>{i.model}</td>
                <td>${Number(i.cost).toLocaleString()}</td>
              </tr>
            ))}
            {req.equipment_items.length === 0 && (
              <tr><td colSpan={5} className="py-1 text-muted">No line items.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section>
        <h2 className="mb-1 font-semibold text-fg">Approval history</h2>
        <ul className="space-y-1 text-sm">
          {req.actions.map((a, idx) => (
            <li key={idx} className="border-b border-border pb-1">
              <span className="font-medium">{a.action}</span>
              {a.level ? ` (L${a.level})` : ''} — {a.actor_name}
              {a.comment ? <span className="text-muted"> · "{a.comment}"</span> : null}
            </li>
          ))}
          {req.actions.length === 0 && <li className="text-muted">No actions yet.</li>}
        </ul>
      </section>

      <section>
        <h2 className="mb-1 font-semibold text-fg">Attachments</h2>
        <ul className="space-y-1 text-sm">
          {req.attachments.map((a) => (
            <li key={a.id} className="flex items-center gap-3">
              <a className="text-accent hover:underline" href={attachmentUrl(id, a.id)}>{a.filename}</a>
              <span className="text-xs text-muted">{(a.size / 1024).toFixed(1)} KB</span>
              {canEdit && (
                <button className="text-xs text-red-600 dark:text-red-400" disabled={busy}
                  onClick={() => act(() => deleteAttachment(id, a.id))}>Remove</button>
              )}
            </li>
          ))}
          {req.attachments.length === 0 && <li className="text-muted">No attachments.</li>}
        </ul>
        {canEdit && (
          <div className="mt-2">
            <input type="file" ref={fileRef} className="text-sm" />
            <Button className="ml-2" disabled={busy} onClick={() => {
              const f = fileRef.current?.files?.[0]
              if (f) act(() => uploadAttachment(id, f))
            }}>Upload</Button>
          </div>
        )}
      </section>

      {err && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{err}</p>}

      {hasActions && (
        <section className="space-y-3 border-t border-border pt-4">
          {isAssignee && (
            <div className="space-y-2">
              <Input placeholder="Comment (required to reject)" value={comment}
                onChange={(e) => setComment(e.target.value)} />
              <div className="flex gap-2">
                <Button disabled={busy} onClick={() => act(() => approveRequest(id, comment || undefined))}>Approve</Button>
                <Button className="bg-red-600 text-white hover:bg-red-700" disabled={busy || !comment.trim()}
                  onClick={() => act(() => rejectRequest(id, comment))}>Reject</Button>
              </div>
            </div>
          )}
          {canEdit && <Link className="block text-accent hover:underline" to={`/requests/${id}/edit`}>Edit draft</Link>}
          {canResubmit && <Button disabled={busy} onClick={() => act(() => resubmitRequest(id))}>Resubmit</Button>}
          {canFinance && <FinanceForm disabled={busy} onSubmit={(costs) => act(() => completeFinance(id, costs))} />}
        </section>
      )}
      </BrandCard>

      <button className="text-sm text-muted hover:text-fg" onClick={() => navigate('/')}>← Back to dashboard</button>
    </div>
  )
}

const FINANCE_FIELDS: [string, string][] = [
  ['cost_autos_trucks', 'Autos & Trucks'], ['cost_machinery', 'Machinery & Equipment'],
  ['cost_improvements', 'Improvements'], ['cost_furniture', 'Furniture & Fixtures'],
  ['cost_permits', 'Permits'], ['cost_misc', 'Misc'],
]

function FinanceForm({ onSubmit, disabled }:
  { onSubmit: (costs: Record<string, string | null>) => void; disabled: boolean }) {
  const [vals, setVals] = useState<Record<string, string>>({})
  return (
    <div className="space-y-2">
      <h2 className="font-semibold text-fg">Complete finance cost breakdown</h2>
      <div className="grid grid-cols-2 gap-2">
        {FINANCE_FIELDS.map(([key, label]) => (
          <div key={key} className="space-y-1">
            <label className="text-xs text-muted">{label}</label>
            <Input type="number" value={vals[key] ?? ''}
              onChange={(e) => setVals({ ...vals, [key]: e.target.value })} />
          </div>
        ))}
      </div>
      <Button disabled={disabled}
        onClick={() => onSubmit(Object.fromEntries(FINANCE_FIELDS.map(([k]) => [k, vals[k]?.trim() ? vals[k] : null])))}>
        Save finance section
      </Button>
    </div>
  )
}
