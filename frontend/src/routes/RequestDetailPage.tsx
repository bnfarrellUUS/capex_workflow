import { useState, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getRequest, approveRequest, rejectRequest, resubmitRequest, completeFinance,
  deleteRequest, uploadAttachment, deleteAttachment, attachmentUrl,
  type CapexRequestData,
} from '../api/requests'
import { FINANCE_FIELDS, parseFinanceCosts, financeFormValues, financeTotalCents, dollars } from './financeCosts'
import { useMe } from '../auth/useMe'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { BrandCard } from '../components/ui/BrandCard'
import { StatusBadge } from '../components/ui/Badge'
import {
  ApproveIcon, RejectIcon, SubmitIcon, EditIcon, DeleteIcon, UploadIcon, DownloadIcon,
} from '../components/ActionIcons'

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
  const canFinance = me.roles.includes('FINANCE') && req.status === 'APPROVED'
  const canAttach = canEdit || canFinance
  const hasActions = isAssignee || canEdit || canResubmit

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
        mark="requests"
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
            <tr className="bg-brand-navy text-left text-xs uppercase tracking-wide text-white [&>th]:py-1.5 [&>th:first-child]:pl-2 [&>th:last-child]:pr-2">
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
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-brand-navy text-left text-xs uppercase tracking-wide text-white [&>th]:py-1.5 [&>th:first-child]:pl-2 [&>th:last-child]:pr-2">
              <th className="py-1">Action</th><th>Level</th><th>By</th><th>Date</th><th>Comment</th>
            </tr>
          </thead>
          <tbody>
            {req.actions.map((a, idx) => (
              <tr key={idx} className="border-b border-border">
                <td className="py-1 font-medium">{a.action}</td>
                <td>{a.level ? `L${a.level}` : '—'}</td>
                <td>{a.actor_name ?? '—'}</td>
                <td>{formatActionDate(a.created_at)}</td>
                <td className="text-muted">{a.comment || '—'}</td>
              </tr>
            ))}
            {req.actions.length === 0 && (
              <tr><td colSpan={5} className="py-1 text-muted">No actions yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      {req.status === 'APPROVED' && (
        <section>
          <h2 className="mb-1 font-semibold text-fg">Finance cost breakdown</h2>
          {canFinance ? (
            <FinanceForm req={req} disabled={busy} onSubmit={(costs) => act(() => completeFinance(id, costs))} />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {FINANCE_FIELDS.map(([key, label]) => (
                  <div key={key}>
                    <span className="font-medium">{label}:</span>{' '}
                    {req[key] != null ? `$${Number(req[key]).toLocaleString()}` : '—'}
                  </div>
                ))}
              </div>
              <BreakdownTotal vals={financeFormValues(req)} requestTotal={req.total_cost} />
              {!req.finance_completed && (
                <p className="mt-1 text-sm text-muted">Not completed by Finance yet.</p>
              )}
            </>
          )}
        </section>
      )}

      <section>
        <h2 className="mb-1 font-semibold text-fg">Attachments</h2>
        <ul className="space-y-1 text-sm">
          {req.attachments.map((a) => (
            <li key={a.id} className="flex items-center gap-3">
              <a className="inline-flex items-center gap-1.5 text-accent hover:underline" href={attachmentUrl(id, a.id)}>
                <DownloadIcon size={15} />{a.filename}
              </a>
              <span className="text-xs text-muted">{(a.size / 1024).toFixed(1)} KB</span>
              {canAttach && (
                <button className="inline-flex items-center gap-1 text-xs text-red-600 dark:text-red-400" disabled={busy}
                  onClick={() => act(() => deleteAttachment(id, a.id))}><DeleteIcon size={13} />Remove</button>
              )}
            </li>
          ))}
          {req.attachments.length === 0 && <li className="text-muted">No attachments.</li>}
        </ul>
        {canAttach && (
          <div className="mt-2">
            <input type="file" ref={fileRef} className="hidden" onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) act(() => uploadAttachment(id, f))
              e.target.value = ''
            }} />
            <Button disabled={busy} onClick={() => fileRef.current?.click()}>
              <UploadIcon size={16} />Attach file
            </Button>
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
                <Button disabled={busy} onClick={() => act(() => approveRequest(id, comment || undefined))}>
                  <ApproveIcon size={16} />Approve
                </Button>
                <Button className="bg-red-600 text-white hover:bg-red-700" disabled={busy || !comment.trim()}
                  onClick={() => act(() => rejectRequest(id, comment))}>
                  <RejectIcon size={16} />Reject
                </Button>
              </div>
            </div>
          )}
          {canEdit && (
            <div className="flex flex-wrap items-center gap-4">
              <Link className="inline-flex items-center gap-1.5 text-accent hover:underline" to={`/requests/${id}/edit`}>
                <EditIcon size={16} />Edit draft
              </Link>
              {isOwner && req.status === 'DRAFT' && (
                <Button className="bg-red-600 text-white hover:bg-red-700" disabled={busy}
                  onClick={async () => {
                    if (!window.confirm(`Delete draft ${req.number}? This cannot be undone.`)) return
                    setErr(null)
                    setBusy(true)
                    try {
                      await deleteRequest(id)
                      navigate('/requests', { replace: true })
                    } catch (e) {
                      setErr(e instanceof ApiError ? e.message : 'Delete failed.')
                      setBusy(false)
                    }
                  }}>
                  <DeleteIcon size={16} />Delete draft
                </Button>
              )}
              {canResubmit && (
                <Button disabled={busy} onClick={() => act(() => resubmitRequest(id))}>
                  <SubmitIcon size={16} />Resubmit
                </Button>
              )}
            </div>
          )}
        </section>
      )}
      </BrandCard>

      <button className="text-sm text-muted hover:text-fg" onClick={() => navigate('/')}>← Back to dashboard</button>
    </div>
  )
}

function formatActionDate(iso: string | null): string {
  if (!iso) return '—'
  // Backend timestamps are UTC; older rows may arrive without a zone marker.
  const d = new Date(/Z|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}

function BreakdownTotal({ vals, requestTotal }: {
  vals: Record<string, string>
  requestTotal: string | null
}) {
  const totalCents = financeTotalCents(vals)
  const requestCents = Math.round(Number(requestTotal ?? 0) * 100)
  const matches = totalCents === requestCents
  return (
    <div className="text-sm">
      <p>
        Breakdown total: <span className="font-medium">${dollars(totalCents)}</span>
        {' '}· CAPEX total: <span className="font-medium">${dollars(requestCents)}</span>
        {matches
          ? <span className="ml-2 font-medium text-green-600 dark:text-green-400">✓ Matches</span>
          : <span className="ml-2 text-amber-600 dark:text-amber-400">
              ${dollars(Math.abs(requestCents - totalCents))} {totalCents < requestCents ? 'left to allocate' : 'over the CAPEX total'}
            </span>}
      </p>
      <p className="text-xs text-muted">The CAPEX total is the sum of the equipment line items.</p>
    </div>
  )
}

function FinanceForm({ req, onSubmit, disabled }: {
  req: CapexRequestData
  onSubmit: (costs: Record<string, string | null>) => void
  disabled: boolean
}) {
  const [vals, setVals] = useState<Record<string, string>>(() => financeFormValues(req))
  const [formErr, setFormErr] = useState<string | null>(null)
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted">Allocate the total cost across categories, in dollars.</p>
      <div className="grid grid-cols-2 gap-2">
        {FINANCE_FIELDS.map(([key, label]) => (
          <div key={key} className="space-y-1">
            <label className="text-xs text-muted">{label} ($)</label>
            <Input inputMode="decimal" placeholder="0.00" value={vals[key] ?? ''}
              onChange={(e) => setVals({ ...vals, [key]: e.target.value })} />
          </div>
        ))}
      </div>
      <BreakdownTotal vals={vals} requestTotal={req.total_cost} />
      {formErr && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{formErr}</p>}
      <Button disabled={disabled}
        onClick={() => {
          const { costs, invalid } = parseFinanceCosts(vals)
          if (invalid.length) {
            setFormErr(`Enter dollar amounts only — check: ${invalid.join(', ')}.`)
            return
          }
          setFormErr(null)
          onSubmit(costs)
        }}>
        {req.finance_completed ? 'Update finance section' : 'Save finance section'}
      </Button>
    </div>
  )
}
