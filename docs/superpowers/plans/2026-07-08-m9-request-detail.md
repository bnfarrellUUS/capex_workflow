# M9 — Request Detail Page + Decision UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A request detail page showing all fields, a status pipeline, and the append-only approval history, with contextual actions — Approve/Reject (assignee), Edit/Resubmit (requestor), Complete Finance (Finance) — wired to the M8 endpoints.

**Architecture:** Extend `request_out` with display names and the serialized `ApprovalAction` history. A `RequestDetailPage` decides which actions to show from the viewer (`useMe`) vs the request's `requestor_id`/`assignee_id`/`status`/roles. Submit and decisions land on the detail page.

**Tech Stack:** Flask, React, TanStack Query. Builds on M1–M8.

## Global Constraints
- Inherits all prior constraints. Actions are gated in the UI AND enforced server-side (M6/M8). Reject requires a comment.

---

### Task 1: Extend request_out with names + approval history

**Files:**
- Modify: `backend/app/services/request_service.py` (`request_out`)
- Modify: `backend/tests/test_request_service.py` (assert names + actions)

- [ ] **Step 1: Add a failing assertion** — append to `test_request_service.py`:
```python
def test_request_out_includes_names_and_actions(app):
    from app.services.workflow_service import submit
    from tests.factories import make_user, make_division, set_thresholds, make_draft
    approver = make_user("appr")
    requestor = make_user("req2", roles='["REQUESTOR"]')
    div = make_division(number="900", l1_approver_id=approver.id)
    set_thresholds()
    r = make_draft(requestor.id, div.id, costs=("30000",), number="CX000900")
    submit(r.id, requestor.id)
    out = request_service.request_out(request_service.get_request(r.id, requestor))
    assert out["requestor_name"] == requestor.name
    assert out["assignee_name"] == approver.name
    assert out["division_name"].startswith("900")
    assert any(a["action"] == "SUBMITTED" and a["actor_name"] == requestor.name for a in out["actions"])
```

- [ ] **Step 2: Run → fail.** `pytest tests/test_request_service.py::test_request_out_includes_names_and_actions -v`

- [ ] **Step 3: Extend `request_out`** — before the final `return {...}`'s closing brace, add these keys (inside the dict):
```python
        "requestor_name": req.requestor.name if req.requestor else None,
        "assignee_name": req.assignee.name if req.assignee else None,
        "division_name": f"{req.division.number} — {req.division.name}" if req.division else None,
        "actions": [
            {"action": a.action, "level": a.level, "comment": a.comment,
             "created_at": a.created_at.isoformat() if a.created_at else None,
             "actor_name": a.actor.name if a.actor else None}
            for a in sorted(req.actions, key=lambda x: x.created_at or x.id)
        ],
```

- [ ] **Step 4: Run → pass.** Then `pytest tests/test_request_service.py -q`.

- [ ] **Step 5: Commit** — `git add backend/app/services/request_service.py backend/tests/test_request_service.py && git commit -m "feat(backend): include display names + approval history in request serialization"`

---

### Task 2: Detail page + decision actions

**Files:**
- Modify: `frontend/src/api/requests.ts` (types + action calls)
- Create: `frontend/src/routes/RequestDetailPage.tsx`
- Modify: `frontend/src/App.tsx` (add `/requests/:id` route)
- Modify: `frontend/src/routes/WizardPage.tsx` (submit → navigate to detail)

- [ ] **Step 1: API additions** — in `frontend/src/api/requests.ts`, extend the interface and add calls:
  - add to `CapexRequestData`:
```ts
  requestor_id: string
  assignee_id: string | null
  requestor_name: string | null
  assignee_name: string | null
  division_name: string | null
  finance_completed: boolean
  actions: { action: string; level: number | null; comment: string | null; created_at: string | null; actor_name: string | null }[]
```
  - add functions:
```ts
export function approveRequest(id: string, comment?: string) {
  return api<CapexRequestData>(`/requests/${id}/approve`, { method: 'POST', body: { comment } })
}
export function rejectRequest(id: string, comment: string) {
  return api<CapexRequestData>(`/requests/${id}/reject`, { method: 'POST', body: { comment } })
}
export function resubmitRequest(id: string) {
  return api<CapexRequestData>(`/requests/${id}/resubmit`, { method: 'POST' })
}
export function completeFinance(id: string, costs: Record<string, string | null>) {
  return api<CapexRequestData>(`/requests/${id}/finance`, { method: 'POST', body: costs })
}
```

- [ ] **Step 2: Detail page** — `frontend/src/routes/RequestDetailPage.tsx`:
```tsx
import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getRequest, approveRequest, rejectRequest, resubmitRequest, completeFinance,
} from '../api/requests'
import { useMe } from '../auth/useMe'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

const PIPELINE = ['DRAFT', 'PENDING_L1', 'PENDING_L2', 'PENDING_L3', 'APPROVED']

export default function RequestDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: me } = useMe()
  const { data: req } = useQuery({ queryKey: ['request', id], queryFn: () => getRequest(id) })
  const [comment, setComment] = useState('')
  const [err, setErr] = useState<string | null>(null)

  const refresh = (updated: unknown) => { qc.setQueryData(['request', id], updated) }
  const run = (fn: () => Promise<unknown>) => {
    setErr(null)
    fn().then(refresh).catch((e) => setErr(e instanceof ApiError ? e.message : 'Action failed.'))
  }

  const approve = useMutation({ mutationFn: () => approveRequest(id, comment || undefined), onSuccess: refresh })
  const reject = useMutation({ mutationFn: () => rejectRequest(id, comment), onSuccess: refresh })
  const resubmit = useMutation({ mutationFn: () => resubmitRequest(id), onSuccess: refresh })

  if (!req || !me) return <p className="text-sm text-slate-500">Loading…</p>

  const isAssignee = req.assignee_id === me.id && req.status.startsWith('PENDING_')
  const isOwner = req.requestor_id === me.id
  const canEdit = isOwner && (req.status === 'DRAFT' || req.status === 'REJECTED')
  const canResubmit = isOwner && req.status === 'REJECTED'
  const canFinance = me.roles.includes('FINANCE') && req.status === 'APPROVED' && !req.finance_completed

  const wrap = (m: { mutate: () => void; error: unknown }) => () => {
    setErr(null); m.mutate()
  }
  const errorText = err
    || (approve.error instanceof ApiError ? approve.error.message : null)
    || (reject.error instanceof ApiError ? reject.error.message : null)

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-brand-navy">Request {req.number}</h1>
        <span className="rounded bg-slate-200 px-2 py-1 text-xs">{req.status}</span>
      </div>

      <ol className="flex flex-wrap gap-2 text-xs">
        {PIPELINE.map((s) => (
          <li key={s} className={`rounded px-2 py-1 ${s === req.status ? 'bg-brand-blue text-white' : 'bg-slate-200 text-slate-600'}`}>{s}</li>
        ))}
        {req.status === 'REJECTED' && <li className="rounded bg-red-600 px-2 py-1 text-white">REJECTED</li>}
      </ol>

      <section className="grid grid-cols-2 gap-2 text-sm">
        <div><span className="font-medium">Requestor:</span> {req.requestor_name}</div>
        <div><span className="font-medium">Division:</span> {req.division_name ?? '—'}</div>
        <div><span className="font-medium">Assignee:</span> {req.assignee_name ?? '—'}</div>
        <div><span className="font-medium">Total cost:</span> ${Number(req.total_cost ?? 0).toLocaleString()}</div>
        <div className="col-span-2"><span className="font-medium">Description:</span> {req.description || '—'}</div>
      </section>

      <section>
        <h2 className="mb-1 font-semibold">Equipment</h2>
        <table className="w-full border-collapse text-sm">
          <thead><tr className="border-b text-left text-slate-500"><th className="py-1">Units</th><th>Type</th><th>Make</th><th>Model</th><th>Cost</th></tr></thead>
          <tbody>
            {req.equipment_items.map((i, idx) => (
              <tr key={idx} className="border-b"><td className="py-1">{i.units}</td><td>{i.type}</td><td>{i.make}</td><td>{i.model}</td><td>${Number(i.cost).toLocaleString()}</td></tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2 className="mb-1 font-semibold">Approval history</h2>
        <ul className="space-y-1 text-sm">
          {req.actions.map((a, idx) => (
            <li key={idx} className="border-b pb-1">
              <span className="font-medium">{a.action}</span>
              {a.level ? ` (L${a.level})` : ''} — {a.actor_name}
              {a.comment ? <span className="text-slate-600"> · "{a.comment}"</span> : null}
            </li>
          ))}
          {req.actions.length === 0 && <li className="text-slate-500">No actions yet.</li>}
        </ul>
      </section>

      {errorText && <p className="text-sm text-red-600" role="alert">{errorText}</p>}

      {(isAssignee || canResubmit || canEdit || canFinance) && (
        <section className="space-y-3 border-t pt-4">
          {(isAssignee) && (
            <div className="space-y-2">
              <Input placeholder="Comment (required to reject)" value={comment}
                onChange={(e) => setComment(e.target.value)} />
              <div className="flex gap-2">
                <Button disabled={approve.isPending} onClick={wrap(approve)}>Approve</Button>
                <Button className="bg-red-600 hover:bg-red-700" disabled={reject.isPending}
                  onClick={wrap(reject)}>Reject</Button>
              </div>
            </div>
          )}
          {canEdit && <Link className="text-brand-blue hover:underline" to={`/requests/${id}/edit`}>Edit draft</Link>}
          {canResubmit && <Button disabled={resubmit.isPending} onClick={wrap(resubmit)}>Resubmit</Button>}
          {canFinance && <FinanceForm onSubmit={(costs) => run(() => completeFinance(id, costs))} />}
        </section>
      )}

      <button className="text-sm text-slate-500" onClick={() => navigate('/')}>← Back to dashboard</button>
    </div>
  )
}

const FINANCE_FIELDS: [string, string][] = [
  ['cost_autos_trucks', 'Autos & Trucks'], ['cost_machinery', 'Machinery & Equipment'],
  ['cost_improvements', 'Improvements'], ['cost_furniture', 'Furniture & Fixtures'],
  ['cost_permits', 'Permits'], ['cost_misc', 'Misc'],
]

function FinanceForm({ onSubmit }: { onSubmit: (costs: Record<string, string | null>) => void }) {
  const [vals, setVals] = useState<Record<string, string>>({})
  return (
    <div className="space-y-2">
      <h2 className="font-semibold">Complete finance cost breakdown</h2>
      <div className="grid grid-cols-2 gap-2">
        {FINANCE_FIELDS.map(([key, label]) => (
          <div key={key} className="space-y-1">
            <label className="text-xs text-slate-500">{label}</label>
            <Input type="number" value={vals[key] ?? ''} onChange={(e) => setVals({ ...vals, [key]: e.target.value })} />
          </div>
        ))}
      </div>
      <Button onClick={() => onSubmit(Object.fromEntries(FINANCE_FIELDS.map(([k]) => [k, vals[k]?.trim() ? vals[k] : null])))}>
        Save finance section
      </Button>
    </div>
  )
}
```

- [ ] **Step 3: Route + wizard redirect** —
  - `App.tsx`: add `import RequestDetailPage from './routes/RequestDetailPage'` and `<Route path="/requests/:id" element={<RequestDetailPage />} />` (inside ProtectedLayout).
  - `WizardPage.tsx`: change submit `onSuccess` to `navigate(\`/requests/${id}\`, { replace: true })`.

- [ ] **Step 4: Build** — `./node_modules/.bin/tsc && ./node_modules/.bin/vite build` → no errors.

- [ ] **Step 5: Commit** — `git add frontend/src && git commit -m "feat(frontend): request detail page with approve/reject/resubmit/finance actions"`

---

### Task 3: Browser smoke — full lifecycle

- [ ] **Step 1:** Backend + frontend running. As **admin**, set division 100's L1 approver to an approver user (or reuse jsmith) and assign a requestor to division 100 (admin UI). Log in as the requestor, New Request → fill equipment → Submit → lands on detail page showing `PENDING_L1` and a SUBMITTED history entry.
- [ ] **Step 2:** Log in as the assignee (approver), open `/requests/<id>`, click Approve → status becomes `PENDING_L2`/`APPROVED` with an APPROVED history entry. Screenshot the detail page.
- [ ] **Step 3:** (no commit — verification only)

---

## Self-Review
- **Coverage:** detail view + status pipeline + history (§6 screen 4) → T1/T2; approve/reject/resubmit/finance actions → T2 (wired to M8 endpoints). Search/list is M11.
- **Placeholders:** none.
- **Types:** `CapexRequestData` extended to match the new `request_out` keys; action calls hit the M8 routes; query key `['request', id]` shared with the wizard.
