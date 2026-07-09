# M11 — Request Lists + Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** A My Requests / Assigned-to-me list with status filter, a dashboard approvals queue, and a final end-to-end verification — completing the Flask + React rebuild.

**Architecture:** `list_requests(viewer, scope, status, division_id)` + a light `request_summary`; a `GET /api/requests` list endpoint. Frontend `RequestsListPage` (scope toggle + status filter) and a dashboard "My Approvals" queue. A short root README documents the finished two-app setup.

**Tech Stack:** Flask, React, pytest. Builds on M1–M10.

## Global Constraints
- Inherits all prior. `scope=mine` → own requests; `scope=assigned` → assigned to viewer; `scope=all` → only if ADMIN/FINANCE (else falls back to mine).

---

### Task 1: list_requests + summary + list endpoint

**Files:**
- Modify: `backend/app/services/request_service.py` (`list_requests`, `request_summary`)
- Modify: `backend/app/blueprints/requests.py` (`GET /api/requests`)
- Test: `backend/tests/test_request_list.py`

- [ ] **Step 1: Failing tests** — `backend/tests/test_request_list.py`:
```python
from app.extensions import db
from app.models import User
from app.services.security import hash_password
from app.services import request_service
from app.services.workflow_service import submit
from tests.factories import make_user, make_division, set_thresholds


def _login(client, user):
    client.post("/api/auth/login", json={"username": user.username, "password": "secret123"})


def test_list_scope_mine(client, app):
    a = make_user("a", roles='["REQUESTOR"]')
    b = make_user("b", roles='["REQUESTOR"]')
    request_service.create_draft(a)
    request_service.create_draft(b)
    _login(client, a)
    rows = client.get("/api/requests?scope=mine").get_json()
    assert len(rows) == 1


def test_list_scope_assigned(client, app):
    approver = make_user("appr")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    requestor.division_id = div.id
    set_thresholds()
    db.session.commit()
    d = request_service.create_draft(requestor)
    request_service.update_draft(d.id, requestor, {"equipment_items": [
        {"units": 1, "condition": "NEW", "type": "T", "make": "M", "model": "Mo", "cost": "30000"}]})
    submit(d.id, requestor.id)
    _login(client, approver)
    rows = client.get("/api/requests?scope=assigned").get_json()
    assert len(rows) == 1 and rows[0]["status"] == "PENDING_L1"


def test_status_filter(client, app):
    a = make_user("a", roles='["REQUESTOR"]')
    request_service.create_draft(a)  # DRAFT
    _login(client, a)
    assert len(client.get("/api/requests?scope=mine&status=DRAFT").get_json()) == 1
    assert len(client.get("/api/requests?scope=mine&status=APPROVED").get_json()) == 0
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Service** — add to `request_service.py`:
```python
def list_requests(viewer, scope="mine", status=None, division_id=None):
    from app.models import CapexRequest
    q = db.session.query(CapexRequest)
    if scope == "assigned":
        q = q.filter(CapexRequest.assignee_id == viewer.id)
    elif scope == "all" and ("ADMIN" in viewer.roles_list or "FINANCE" in viewer.roles_list):
        pass
    else:
        q = q.filter(CapexRequest.requestor_id == viewer.id)
    if status:
        q = q.filter(CapexRequest.status == status)
    if division_id:
        q = q.filter(CapexRequest.division_id == division_id)
    return q.order_by(CapexRequest.created_at.desc()).all()


def request_summary(req):
    return {
        "id": req.id, "number": req.number, "status": req.status,
        "total_cost": money_str(req.total_cost),
        "division_name": f"{req.division.number} — {req.division.name}" if req.division else None,
        "requestor_name": req.requestor.name if req.requestor else None,
        "assignee_name": req.assignee.name if req.assignee else None,
        "current_level": req.current_level, "required_levels": req.required_levels,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }
```
(`db` is already imported at module top.)

- [ ] **Step 4: Endpoint** — add to `requests.py` (before `create_request`, a `GET ""`):
```python
@bp.get("")
@login_required
def list_requests_route():
    rows = request_service.list_requests(
        current_user,
        scope=request.args.get("scope", "mine"),
        status=request.args.get("status") or None,
        division_id=request.args.get("division_id") or None,
    )
    return jsonify([request_service.request_summary(r) for r in rows])
```

- [ ] **Step 5: Run → pass.** `pytest tests/test_request_list.py -v`; then `pytest -q`.

- [ ] **Step 6: Commit** — `git add backend/app/services/request_service.py backend/app/blueprints/requests.py backend/tests/test_request_list.py && git commit -m "feat(backend): request list endpoint (scope + status filter)"`

---

### Task 2: Requests list page + dashboard approvals queue

**Files:**
- Modify: `frontend/src/api/requests.ts` (`RequestSummary`, `listRequests`)
- Create: `frontend/src/routes/RequestsListPage.tsx`
- Modify: `frontend/src/routes/DashboardPage.tsx` (approvals queue)
- Modify: `frontend/src/components/AppShell.tsx` (add "My Requests")
- Modify: `frontend/src/App.tsx` (route `/requests`)

- [ ] **Step 1: API** — add to `requests.ts`:
```ts
export interface RequestSummary {
  id: string
  number: string
  status: string
  total_cost: string | null
  division_name: string | null
  requestor_name: string | null
  assignee_name: string | null
  created_at: string | null
}

export function listRequests(params: { scope?: string; status?: string } = {}): Promise<RequestSummary[]> {
  const q = new URLSearchParams()
  if (params.scope) q.set('scope', params.scope)
  if (params.status) q.set('status', params.status)
  const qs = q.toString()
  return api<RequestSummary[]>(`/requests${qs ? `?${qs}` : ''}`)
}
```

- [ ] **Step 2: A shared table** — `frontend/src/routes/RequestsListPage.tsx`:
```tsx
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listRequests } from '../api/requests'
import { Select } from '../components/ui/Select'

const STATUSES = ['', 'DRAFT', 'PENDING_L1', 'PENDING_L2', 'PENDING_L3', 'APPROVED', 'REJECTED']

export default function RequestsListPage() {
  const [scope, setScope] = useState('mine')
  const [status, setStatus] = useState('')
  const { data: rows = [] } = useQuery({
    queryKey: ['requests', scope, status],
    queryFn: () => listRequests({ scope, status: status || undefined }),
  })

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold text-brand-navy">Requests</h1>
      <div className="mb-4 flex gap-2">
        {(['mine', 'assigned'] as const).map((s) => (
          <button key={s} onClick={() => setScope(s)}
            className={`rounded px-3 py-1 text-sm ${scope === s ? 'bg-brand-blue text-white' : 'bg-slate-200 text-slate-700'}`}>
            {s === 'mine' ? 'My Requests' : 'Assigned to me'}
          </button>
        ))}
        <div className="w-48">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => <option key={s} value={s}>{s === '' ? 'All statuses' : s}</option>)}
          </Select>
        </div>
      </div>
      <RequestsTable rows={rows} />
    </div>
  )
}

export function RequestsTable({ rows }: { rows: import('../api/requests').RequestSummary[] }) {
  if (rows.length === 0) return <p className="text-sm text-slate-500">No requests.</p>
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b text-left text-slate-500">
          <th className="py-2">Number</th><th>Status</th><th>Division</th><th>Requestor</th><th>Total</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="border-b">
            <td className="py-2"><Link className="text-brand-blue hover:underline" to={`/requests/${r.id}`}>{r.number}</Link></td>
            <td>{r.status}</td>
            <td>{r.division_name ?? '—'}</td>
            <td>{r.requestor_name}</td>
            <td>${Number(r.total_cost ?? 0).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

- [ ] **Step 3: Dashboard approvals queue** — replace `DashboardPage.tsx`:
```tsx
import { useQuery } from '@tanstack/react-query'
import { useMe } from '../auth/useMe'
import { listRequests } from '../api/requests'
import { RequestsTable } from './RequestsListPage'

export default function DashboardPage() {
  const { data: user } = useMe()
  const { data: approvals = [] } = useQuery({
    queryKey: ['requests', 'assigned', ''],
    queryFn: () => listRequests({ scope: 'assigned' }),
  })
  return (
    <div className="space-y-6">
      <div>
        <h1 className="mb-1 text-2xl font-semibold text-brand-navy">Dashboard</h1>
        <p className="text-slate-600">Welcome, {user?.name}.</p>
      </div>
      <section>
        <h2 className="mb-2 font-semibold">My approvals</h2>
        <RequestsTable rows={approvals} />
      </section>
    </div>
  )
}
```

- [ ] **Step 4: Nav + route** — `AppShell.tsx` NAV: add `{ to: '/requests', label: 'My Requests', roles: [] as string[] }` after New Request. `App.tsx`: import `RequestsListPage` and add `<Route path="/requests" element={<RequestsListPage />} />` (inside ProtectedLayout, BEFORE `/requests/:id` is fine since `/requests` is exact).

- [ ] **Step 5: Build** — `./node_modules/.bin/tsc && ./node_modules/.bin/vite build` → no errors.

- [ ] **Step 6: Commit** — `git add frontend/src && git commit -m "feat(frontend): requests list page + dashboard approvals queue"`

---

### Task 3: Root README + final verification

**Files:**
- Create: `README.md` (repo root)

- [ ] **Step 1: Root README** — `README.md`:
```markdown
# CAPEX Tracking — United Uptime Services

Internal web app to submit, route, approve, and search capital-expenditure requests.

## Stack
- **backend/** — Flask API (Python), SQLAlchemy, SQLite (dev) / Azure SQL Server (prod)
- **frontend/** — React + Vite + TypeScript SPA (Tailwind, brand colors)

## Run (Windows, Git Bash — the repo path contains `&`)
Double-click **run-app.bat**, or manually:

    # backend
    cd backend && python -m venv .venv && source .venv/Scripts/activate
    pip install -r requirements.txt && flask db upgrade && python seed.py && flask run
    # frontend (separate shell)
    cd frontend && npm install && npm run dev

Backend: http://localhost:5000 · Frontend: http://localhost:5173 · Login: admin / ChangeMe123!

## Test
    cd backend && pytest -q
    cd frontend && npm test && npm run build

Design & plans live in `docs/superpowers/`.
```

- [ ] **Step 2: Full backend suite** — `cd backend && pytest -q` → all pass.

- [ ] **Step 3: Frontend build + tests** — `cd frontend && ./node_modules/.bin/vitest run && ./node_modules/.bin/tsc && ./node_modules/.bin/vite build` → all pass.

- [ ] **Step 4: Browser walk** — backend + frontend running; log in as admin, visit Dashboard (approvals queue), My Requests (filter by status), open a request detail. Screenshot the list.

- [ ] **Step 5: Commit** — `git add README.md && git commit -m "docs: root README for the Flask + React app"`

---

## Self-Review
- **Coverage:** list with scope + status filter (§6 screens 2/5/6), dashboard approvals queue (§6 screen 2), root README/cutover → all tasks. (`capex-app` was removed in M1; launcher updated in M3.) PDF/Excel export remain out of scope per the master deferral.
- **Placeholders:** none.
- **Types:** `RequestSummary` matches `request_summary`; `/requests` GET list vs `/requests/:id` detail are distinct routes; query keys `['requests', scope, status]`.
