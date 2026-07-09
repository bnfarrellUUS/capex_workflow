# M7 — Request Draft + 6-Step Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a Requestor create a draft CAPEX request and fill it out through the 6-step wizard, saving at any step. Draft persists; submit is wired in M8.

**Architecture:** Backend `request_service` (create draft → allocates `CX######` + prefills division; get with access check; save draft = PATCH with lenient validation, owner-only, DRAFT/REJECTED). Frontend: `/requests/new` creates a draft then redirects to `/requests/:id/edit`, a stepper `WizardPage` that loads the request, holds form state, and PATCH-saves. Live equipment cost sum and auto payback in the UI.

**Tech Stack:** Flask, Pydantic, SQLAlchemy, React, TanStack Query, pytest. Builds on M1–M6.

## Global Constraints

- Inherits all prior constraints. API JSON snake_case; money as strings via `money_str`.
- Draft edit is **owner-only**, allowed only while `DRAFT` or `REJECTED`. Empty decimal inputs are sent as `null` (not `""`).
- The wizard has 6 steps (Basic Info; Description & Justification; Effect on Operations; Equipment Requests; Economic Justification; Review). Save Draft on every step. **Submit is added in M8.**

---

### Task 1: Request service (create/get/update draft) + serialization

**Files:**
- Create: `backend/app/services/request_service.py`
- Test: `backend/tests/test_request_service.py`

**Interfaces:**
- Produces:
  - `create_draft(requestor) -> CapexRequest` (allocates number, prefills `division_id` from the requestor).
  - `get_request(request_id, viewer) -> CapexRequest` (access: requestor, assignee, or ADMIN/FINANCE).
  - `update_draft(request_id, viewer, payload: dict) -> CapexRequest` (owner-only, DRAFT/REJECTED; `payload` is `RequestDraft.model_dump(exclude_unset=True)`; `equipment_items` replaces the collection).
  - `request_out(req) -> dict` serializer.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_request_service.py`:
```python
import pytest
from decimal import Decimal

from app.extensions import db
from app.services.errors import ServiceError
from app.services import request_service
from tests.factories import make_user, make_division


def test_create_draft_allocates_number_and_prefills_division(app):
    div = make_division()
    user = make_user("req", roles='["REQUESTOR"]')
    user.division_id = div.id
    db.session.commit()
    draft = request_service.create_draft(user)
    assert draft.number.startswith("CX")
    assert draft.status == "DRAFT"
    assert draft.division_id == div.id


def test_update_draft_sets_fields_and_equipment(app):
    user = make_user("req", roles='["REQUESTOR"]')
    draft = request_service.create_draft(user)
    payload = {
        "description": "Forklift",
        "annual_savings": Decimal("10000"),
        "equipment_items": [
            {"units": 2, "condition": "NEW", "type": "Forklift", "make": "Toyota",
             "model": "8FGU25", "cost": Decimal("30000")},
        ],
    }
    updated = request_service.update_draft(draft.id, user, payload)
    assert updated.description == "Forklift"
    assert len(updated.equipment_items) == 1
    assert updated.equipment_items[0].cost == Decimal("30000")


def test_update_draft_owner_only(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    other = make_user("other", roles='["REQUESTOR"]')
    draft = request_service.create_draft(owner)
    with pytest.raises(ServiceError):
        request_service.update_draft(draft.id, other, {"description": "x"})


def test_get_request_access_for_admin(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    admin = make_user("admin", roles='["ADMIN"]')
    draft = request_service.create_draft(owner)
    assert request_service.get_request(draft.id, admin).id == draft.id


def test_get_request_denied_for_stranger(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    stranger = make_user("stranger", roles='["REQUESTOR"]')
    draft = request_service.create_draft(owner)
    with pytest.raises(ServiceError):
        request_service.get_request(draft.id, stranger)


def test_request_out_serializes_money_as_string(app):
    user = make_user("req", roles='["REQUESTOR"]')
    draft = request_service.create_draft(user)
    request_service.update_draft(draft.id, user, {
        "equipment_items": [{"units": 1, "condition": "NEW", "type": "T", "make": "M",
                             "model": "Mo", "cost": Decimal("30000")}]})
    out = request_service.request_out(request_service.get_request(draft.id, user))
    assert out["equipment_items"][0]["cost"] == "30000"
    assert out["status"] == "DRAFT"
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_request_service.py -v` → FAIL (module missing).

- [ ] **Step 3: Write the service**

`backend/app/services/request_service.py`:
```python
from app.extensions import db
from app.models import CapexRequest, EquipmentItem
from app.serialization import money_str
from app.services.counter_service import next_request_number
from app.services.errors import ServiceError

_EDITABLE_STATUSES = ("DRAFT", "REJECTED")


def create_draft(requestor):
    req = CapexRequest(
        number=next_request_number(),
        requestor_id=requestor.id,
        division_id=requestor.division_id,
        status="DRAFT",
    )
    db.session.add(req)
    db.session.commit()
    return req


def _can_view(req, viewer):
    if viewer.id in (req.requestor_id, req.assignee_id):
        return True
    roles = viewer.roles_list
    return "ADMIN" in roles or "FINANCE" in roles


def get_request(request_id, viewer):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if not _can_view(req, viewer):
        raise ServiceError("You do not have access to this request.", 403)
    return req


def update_draft(request_id, viewer, payload):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if req.requestor_id != viewer.id:
        raise ServiceError("You can only edit your own requests.", 403)
    if req.status not in _EDITABLE_STATUSES:
        raise ServiceError("This request can no longer be edited.")
    data = dict(payload)
    items = data.pop("equipment_items", None)
    for key, value in data.items():
        setattr(req, key, value)
    if items is not None:
        req.equipment_items = [
            EquipmentItem(units=i["units"], condition=i["condition"], type=i["type"],
                          make=i["make"], model=i["model"], cost=i["cost"])
            for i in items
        ]
    db.session.commit()
    return req


def request_out(req):
    return {
        "id": req.id,
        "number": req.number,
        "status": req.status,
        "requestor_id": req.requestor_id,
        "assignee_id": req.assignee_id,
        "division_id": req.division_id,
        "request_date": req.request_date.isoformat() if req.request_date else None,
        "description": req.description,
        "budgeted": req.budgeted,
        "replacement": req.replacement,
        "health_safety": req.health_safety,
        "revenue_generating": req.revenue_generating,
        "environmental": req.environmental,
        "competitive_bids": req.competitive_bids,
        "lease_recommended": req.lease_recommended,
        "justification": req.justification,
        "effect_on_operations": req.effect_on_operations,
        "asset_life": req.asset_life,
        "irr_after_tax": money_str(req.irr_after_tax),
        "first_year_ebit": money_str(req.first_year_ebit),
        "annual_savings": money_str(req.annual_savings),
        "payback_years": money_str(req.payback_years),
        "npv_savings": money_str(req.npv_savings),
        "cost_autos_trucks": money_str(req.cost_autos_trucks),
        "cost_machinery": money_str(req.cost_machinery),
        "cost_improvements": money_str(req.cost_improvements),
        "cost_furniture": money_str(req.cost_furniture),
        "cost_permits": money_str(req.cost_permits),
        "cost_misc": money_str(req.cost_misc),
        "finance_completed": req.finance_completed,
        "total_cost": money_str(req.total_cost),
        "required_levels": req.required_levels,
        "current_level": req.current_level,
        "equipment_items": [
            {"id": i.id, "units": i.units, "condition": i.condition, "type": i.type,
             "make": i.make, "model": i.model, "cost": money_str(i.cost)}
            for i in req.equipment_items
        ],
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_request_service.py -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/request_service.py backend/tests/test_request_service.py
git commit -m "feat(backend): request draft service (create/get/update) + serializer"
```

---

### Task 2: Requests blueprint (create/get/update)

**Files:**
- Create: `backend/app/blueprints/requests.py`
- Modify: `backend/app/__init__.py` (register blueprint)
- Test: `backend/tests/test_requests_api.py`

**Interfaces:**
- Produces (login required): `POST /api/requests` (create draft → 201), `GET /api/requests/<id>`, `PATCH /api/requests/<id>` (save draft via `RequestDraft`).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_requests_api.py`:
```python
from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _login(client, username="req", roles='["REQUESTOR"]'):
    u = User(username=username, email=f"{username}@x.com", name=username.title(),
             password_hash=hash_password("secret123"), roles=roles)
    db.session.add(u)
    db.session.commit()
    client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    return u


def test_create_requires_auth(client):
    assert client.post("/api/requests").status_code == 401


def test_create_and_get_draft(client, app):
    _login(client)
    created = client.post("/api/requests")
    assert created.status_code == 201
    body = created.get_json()
    assert body["number"].startswith("CX") and body["status"] == "DRAFT"
    got = client.get(f"/api/requests/{body['id']}")
    assert got.status_code == 200 and got.get_json()["id"] == body["id"]


def test_patch_saves_draft(client, app):
    _login(client)
    rid = client.post("/api/requests").get_json()["id"]
    r = client.patch(f"/api/requests/{rid}", json={
        "description": "Forklift",
        "equipment_items": [{"units": 1, "condition": "NEW", "type": "Forklift",
                             "make": "Toyota", "model": "8", "cost": "30000"}],
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["description"] == "Forklift"
    assert body["equipment_items"][0]["cost"] == "30000"


def test_cannot_get_others_draft(client, app):
    owner = _login(client, "owner")
    rid = client.post("/api/requests").get_json()["id"]
    # log in as someone else
    _login(client, "other")
    assert client.get(f"/api/requests/{rid}").status_code == 403
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_requests_api.py -v` → FAIL (404 / not registered).

- [ ] **Step 3: Write the blueprint**

`backend/app/blueprints/requests.py`:
```python
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.schemas.request import RequestDraft
from app.services import request_service

bp = Blueprint("requests", __name__, url_prefix="/api/requests")


@bp.post("")
@login_required
def create_request():
    req = request_service.create_draft(current_user)
    return jsonify(request_service.request_out(req)), 201


@bp.get("/<request_id>")
@login_required
def get_request(request_id):
    req = request_service.get_request(request_id, current_user)
    return jsonify(request_service.request_out(req))


@bp.patch("/<request_id>")
@login_required
def update_request(request_id):
    data = RequestDraft(**(request.get_json(silent=True) or {}))
    req = request_service.update_draft(request_id, current_user, data.model_dump(exclude_unset=True))
    return jsonify(request_service.request_out(req))
```

- [ ] **Step 4: Register the blueprint**

`backend/app/__init__.py` — after the profile blueprint:
```python
    from .blueprints.requests import bp as requests_bp
    app.register_blueprint(requests_bp)
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/test_requests_api.py -v` → all PASS. Then `pytest -q` (no regressions).

- [ ] **Step 6: Commit**

```bash
git add backend/app/blueprints/requests.py backend/app/__init__.py backend/tests/test_requests_api.py
git commit -m "feat(backend): requests API (create/get/update draft)"
```

---

### Task 3: Frontend requests API + New Request flow + nav

**Files:**
- Create: `frontend/src/api/requests.ts`
- Create: `frontend/src/routes/NewRequestPage.tsx`
- Modify: `frontend/src/components/AppShell.tsx` (add "New Request" nav)
- Modify: `frontend/src/App.tsx` (add routes)

**Interfaces:**
- Produces: `CapexRequestData`, `EquipItem`, `createDraft`, `getRequest`, `updateDraft`; `/requests/new` (creates draft, redirects to edit).

- [ ] **Step 1: Write the API module**

`frontend/src/api/requests.ts`:
```ts
import { api } from './client'

export interface EquipItem {
  id?: string
  units: number
  condition: string
  type: string
  make: string
  model: string
  cost: string
}

export interface CapexRequestData {
  id: string
  number: string
  status: string
  division_id: string | null
  description: string
  budgeted: boolean
  replacement: boolean
  health_safety: boolean
  revenue_generating: boolean
  environmental: boolean
  competitive_bids: boolean
  lease_recommended: boolean
  justification: string
  effect_on_operations: string
  asset_life: string | null
  irr_after_tax: string | null
  first_year_ebit: string | null
  annual_savings: string | null
  payback_years: string | null
  npv_savings: string | null
  total_cost: string | null
  equipment_items: EquipItem[]
}

export function createDraft(): Promise<CapexRequestData> {
  return api<CapexRequestData>('/requests', { method: 'POST' })
}
export function getRequest(id: string): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}`)
}
export function updateDraft(id: string, patch: Record<string, unknown>): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}`, { method: 'PATCH', body: patch })
}
```

- [ ] **Step 2: Write the New Request redirect page**

`frontend/src/routes/NewRequestPage.tsx`:
```tsx
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { createDraft } from '../api/requests'

export default function NewRequestPage() {
  const navigate = useNavigate()
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    createDraft()
      .then((r) => navigate(`/requests/${r.id}/edit`, { replace: true }))
      .catch(() => navigate('/', { replace: true }))
  }, [navigate])
  return <p className="text-sm text-slate-500">Creating draft…</p>
}
```

- [ ] **Step 3: Add nav link**

`frontend/src/components/AppShell.tsx` — add to the `NAV` array after Dashboard:
```tsx
  { to: '/requests/new', label: 'New Request', roles: [] as string[] },
```

- [ ] **Step 4: Add routes**

`frontend/src/App.tsx` — add import and routes inside `ProtectedLayout` (not admin):
```tsx
import NewRequestPage from './routes/NewRequestPage'
import WizardPage from './routes/WizardPage'
```
```tsx
        <Route path="/requests/new" element={<NewRequestPage />} />
        <Route path="/requests/:id/edit" element={<WizardPage />} />
```
(Note: `WizardPage` is created in Task 4; this import will not compile until then — do Steps 4 and Task 4 together before building.)

- [ ] **Step 5: (build happens at end of Task 4)**

Commit deferred to Task 4 (routes depend on WizardPage).

---

### Task 4: Wizard shell + steps 1–3

**Files:**
- Create: `frontend/src/routes/WizardPage.tsx`
- Create: `frontend/src/routes/wizard/types.ts`

**Interfaces:**
- Produces: `WizardPage` (loads request, holds `RequestForm` state, renders a 6-step stepper with Back/Next/Save Draft), and steps 1–3 fields. Steps 4–6 added in Task 5.

- [ ] **Step 1: Write the form types + helpers**

`frontend/src/routes/wizard/types.ts`:
```ts
import type { CapexRequestData, EquipItem } from '../../api/requests'

export interface RequestForm {
  description: string
  budgeted: boolean
  replacement: boolean
  health_safety: boolean
  revenue_generating: boolean
  environmental: boolean
  competitive_bids: boolean
  lease_recommended: boolean
  justification: string
  effect_on_operations: string
  asset_life: string
  irr_after_tax: string
  first_year_ebit: string
  annual_savings: string
  payback_years: string
  npv_savings: string
  division_id: string
  equipment_items: EquipItem[]
}

export function toForm(r: CapexRequestData): RequestForm {
  return {
    description: r.description ?? '',
    budgeted: r.budgeted, replacement: r.replacement, health_safety: r.health_safety,
    revenue_generating: r.revenue_generating, environmental: r.environmental,
    competitive_bids: r.competitive_bids, lease_recommended: r.lease_recommended,
    justification: r.justification ?? '',
    effect_on_operations: r.effect_on_operations ?? '',
    asset_life: r.asset_life ?? '',
    irr_after_tax: r.irr_after_tax ?? '',
    first_year_ebit: r.first_year_ebit ?? '',
    annual_savings: r.annual_savings ?? '',
    payback_years: r.payback_years ?? '',
    npv_savings: r.npv_savings ?? '',
    division_id: r.division_id ?? '',
    equipment_items: r.equipment_items.map((i) => ({ ...i })),
  }
}

const DEC = (s: string) => (s.trim() === '' ? null : s)

export function toPayload(f: RequestForm): Record<string, unknown> {
  return {
    description: f.description,
    budgeted: f.budgeted, replacement: f.replacement, health_safety: f.health_safety,
    revenue_generating: f.revenue_generating, environmental: f.environmental,
    competitive_bids: f.competitive_bids, lease_recommended: f.lease_recommended,
    justification: f.justification,
    effect_on_operations: f.effect_on_operations,
    asset_life: f.asset_life || null,
    irr_after_tax: DEC(f.irr_after_tax),
    first_year_ebit: DEC(f.first_year_ebit),
    annual_savings: DEC(f.annual_savings),
    payback_years: DEC(f.payback_years),
    npv_savings: DEC(f.npv_savings),
    division_id: f.division_id || null,
    equipment_items: f.equipment_items.map((i) => ({
      units: Number(i.units) || 0, condition: i.condition, type: i.type,
      make: i.make, model: i.model, cost: i.cost.trim() === '' ? '0' : i.cost,
    })),
  }
}

export function equipmentTotal(items: EquipItem[]): number {
  return items.reduce((sum, i) => sum + (Number(i.cost) || 0), 0)
}
```

- [ ] **Step 2: Write the WizardPage (shell + steps 1–3; steps 4–6 filled in Task 5)**

`frontend/src/routes/WizardPage.tsx`:
```tsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getRequest, updateDraft } from '../api/requests'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import type { RequestForm } from './wizard/types'
import { toForm, toPayload, equipmentTotal } from './wizard/types'

const STEPS = ['Basic Info', 'Description', 'Effect on Ops', 'Equipment', 'Economic', 'Review']

export default function WizardPage() {
  const { id = '' } = useParams()
  const { data } = useQuery({ queryKey: ['request', id], queryFn: () => getRequest(id) })
  const [form, setForm] = useState<RequestForm | null>(null)
  const [step, setStep] = useState(0)
  const [saved, setSaved] = useState(false)

  useEffect(() => { if (data && !form) setForm(toForm(data)) }, [data, form])

  const save = useMutation({
    mutationFn: () => updateDraft(id, toPayload(form!)),
    onSuccess: () => setSaved(true),
  })

  if (!form || !data) return <p className="text-sm text-slate-500">Loading…</p>

  const set = <K extends keyof RequestForm>(k: K, v: RequestForm[K]) => {
    setForm({ ...form, [k]: v }); setSaved(false)
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold text-brand-navy">Request {data.number}</h1>
      <ol className="my-4 flex flex-wrap gap-2 text-xs">
        {STEPS.map((label, i) => (
          <li key={label}
            className={`rounded px-2 py-1 ${i === step ? 'bg-brand-blue text-white' : 'bg-slate-200 text-slate-600'}`}>
            {i + 1}. {label}
          </li>
        ))}
      </ol>

      <div className="rounded-md border border-slate-200 bg-white p-6">
        {step === 0 && <BasicInfo form={form} set={set} />}
        {step === 1 && (
          <Field label="Brief description & justification">
            <textarea className="min-h-32 w-full rounded-md border border-slate-300 p-2 text-sm"
              value={form.justification} onChange={(e) => set('justification', e.target.value)} />
          </Field>
        )}
        {step === 2 && (
          <Field label="Effect on operations">
            <textarea className="min-h-32 w-full rounded-md border border-slate-300 p-2 text-sm"
              value={form.effect_on_operations} onChange={(e) => set('effect_on_operations', e.target.value)} />
          </Field>
        )}
        {step === 3 && <Equipment form={form} set={set} />}
        {step === 4 && <Economic form={form} set={set} />}
        {step === 5 && <Review form={form} />}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <Button className="bg-slate-200 text-slate-800 hover:bg-slate-300"
          disabled={step === 0} onClick={() => setStep(step - 1)}>Back</Button>
        <Button className="bg-slate-200 text-slate-800 hover:bg-slate-300"
          disabled={save.isPending} onClick={() => save.mutate()}>Save Draft</Button>
        {saved && <span className="text-sm text-green-700">Saved.</span>}
        <div className="flex-1" />
        {step < STEPS.length - 1 && (
          <Button onClick={() => { save.mutate(); setStep(step + 1) }}>Next</Button>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-sm font-medium">{label}</label>
      {children}
    </div>
  )
}

const FLAGS: [keyof RequestForm, string][] = [
  ['budgeted', 'Budgeted'], ['replacement', 'Replacement equipment'],
  ['health_safety', 'Health & safety driven'], ['revenue_generating', 'Revenue generating'],
  ['environmental', 'Environmental / sustainability'], ['competitive_bids', 'Competitive bids received'],
  ['lease_recommended', 'Lease recommended'],
]

function BasicInfo({ form, set }: { form: RequestForm; set: <K extends keyof RequestForm>(k: K, v: RequestForm[K]) => void }) {
  return (
    <div className="space-y-4">
      <Field label="Equipment / project description">
        <Input value={form.description} onChange={(e) => set('description', e.target.value)} />
      </Field>
      <fieldset className="space-y-1">
        <legend className="text-sm font-medium">Flags</legend>
        {FLAGS.map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form[key] as boolean}
              onChange={(e) => set(key, e.target.checked as never)} />
            {label}
          </label>
        ))}
      </fieldset>
    </div>
  )
}

function Equipment({ form, set }: { form: RequestForm; set: <K extends keyof RequestForm>(k: K, v: RequestForm[K]) => void }) {
  const items = form.equipment_items
  const update = (idx: number, patch: Partial<typeof items[number]>) =>
    set('equipment_items', items.map((it, i) => (i === idx ? { ...it, ...patch } : it)))
  const add = () => set('equipment_items', [...items, { units: 1, condition: 'NEW', type: '', make: '', model: '', cost: '' }])
  const remove = (idx: number) => set('equipment_items', items.filter((_, i) => i !== idx))
  return (
    <div className="space-y-3">
      {items.map((it, idx) => (
        <div key={idx} className="flex flex-wrap items-end gap-2 border-b pb-2">
          <LabeledInput label="Units" value={String(it.units)} onChange={(v) => update(idx, { units: Number(v) || 0 })} w="w-16" />
          <LabeledInput label="Type" value={it.type} onChange={(v) => update(idx, { type: v })} />
          <LabeledInput label="Make" value={it.make} onChange={(v) => update(idx, { make: v })} />
          <LabeledInput label="Model" value={it.model} onChange={(v) => update(idx, { model: v })} />
          <LabeledInput label="Cost" value={it.cost} onChange={(v) => update(idx, { cost: v })} w="w-28" />
          <button className="text-sm text-red-600" onClick={() => remove(idx)}>Remove</button>
        </div>
      ))}
      <button className="text-sm text-brand-blue" onClick={add}>+ Add line item</button>
      <div className="text-right font-semibold">Equipment total: ${equipmentTotal(items).toLocaleString()}</div>
    </div>
  )
}

function LabeledInput({ label, value, onChange, w = 'w-40' }:
  { label: string; value: string; onChange: (v: string) => void; w?: string }) {
  return (
    <div className={`space-y-1 ${w}`}>
      <label className="text-xs text-slate-500">{label}</label>
      <Input value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

function Economic({ form, set }: { form: RequestForm; set: <K extends keyof RequestForm>(k: K, v: RequestForm[K]) => void }) {
  const total = equipmentTotal(form.equipment_items)
  const annual = Number(form.annual_savings) || 0
  const autoPayback = annual > 0 ? (total / annual).toFixed(2) : ''
  return (
    <div className="grid grid-cols-2 gap-4">
      <LabeledInput label="Asset / project life" value={form.asset_life} onChange={(v) => set('asset_life', v)} w="" />
      <LabeledInput label="IRR after tax (%)" value={form.irr_after_tax} onChange={(v) => set('irr_after_tax', v)} w="" />
      <LabeledInput label="First-year EBIT" value={form.first_year_ebit} onChange={(v) => set('first_year_ebit', v)} w="" />
      <LabeledInput label="Annual savings" value={form.annual_savings} onChange={(v) => set('annual_savings', v)} w="" />
      <div className="space-y-1">
        <label className="text-xs text-slate-500">Payback (years) — auto: {autoPayback || '—'}</label>
        <Input value={form.payback_years} placeholder={autoPayback}
          onChange={(e) => set('payback_years', e.target.value)} />
      </div>
      <LabeledInput label="NPV of future savings" value={form.npv_savings} onChange={(v) => set('npv_savings', v)} w="" />
    </div>
  )
}

function Review({ form }: { form: RequestForm }) {
  const total = equipmentTotal(form.equipment_items)
  return (
    <div className="space-y-2 text-sm">
      <p><span className="font-medium">Description:</span> {form.description || '—'}</p>
      <p><span className="font-medium">Equipment lines:</span> {form.equipment_items.length}</p>
      <p><span className="font-medium">Total cost:</span> ${total.toLocaleString()}</p>
      <p className="text-slate-500">Submit will be enabled in the next milestone.</p>
    </div>
  )
}
```

- [ ] **Step 3: Build**

Run (from `frontend/`): `./node_modules/.bin/tsc && ./node_modules/.bin/vite build` → no errors.

- [ ] **Step 4: Commit (Tasks 3 + 4 together)**

```bash
git add frontend/src
git commit -m "feat(frontend): request draft creation + 6-step wizard (steps 1-6 UI, save draft)"
```

---

### Task 5: Browser smoke — create, fill, save, persist

**Files:** none (verification only).

- [ ] **Step 1: Run servers and drive the wizard**

Start backend (:5000) + `vite` (:5173). Log in as `admin`, click **New Request** in the nav → lands on `/requests/:id/edit` showing "Request CX…". Fill Basic Info (description + a flag), Next → Description, Next → Effect on Ops, Next → Equipment: add a line item (Type/Make/Model/Cost 30000) and confirm the live "Equipment total: $30,000", Next → Economic (enter annual savings, confirm auto payback shows), Next → Review (shows total). Click **Save Draft** → "Saved."

- [ ] **Step 2: Confirm persistence**

Reload the page (`/requests/:id/edit`) and confirm the description, equipment line, and economic values reloaded from the server. Screenshot the Equipment step.

- [ ] **Step 3: (no commit — verification only)**

---

## Self-Review

**Spec coverage (spec §6 screen 3 wizard, §3 draft-lenient validation, §14 M7 slice):**
- Draft create (auto number, division prefill) + save + access-checked get → Tasks 1–2. ✓
- 6-step stepper with Save Draft, live equipment sum, auto payback → Tasks 3–4. ✓
- Owner-only editing while DRAFT/REJECTED → Task 1. ✓
- Submit intentionally deferred to M8 (Review step notes it). Attachments are M10.

**Placeholder scan:** No TBD/TODO. The Task 3 note about `WizardPage` importing before Task 4 is a sequencing instruction (build after Task 4), not a code placeholder. ✓

**Type consistency:** `CapexRequestData`/`EquipItem` match `request_out` JSON (snake_case, money as strings). `toForm`/`toPayload` round-trip the same fields; `toPayload` sends `null` for empty decimals (backend `RequestDraft` optional Decimals). `updateDraft(id, patch)` matches the PATCH endpoint. Query key `['request', id]`. ✓
