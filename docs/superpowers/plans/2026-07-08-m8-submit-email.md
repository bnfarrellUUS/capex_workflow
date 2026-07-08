# M8 — Submit Wiring + Email Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Expose the M6 workflow engine over HTTP (submit / approve / reject / resubmit / finance) with best-effort email notifications, and wire the wizard's Submit button.

**Architecture:** A `notify` adapter logs to console and writes `NotificationLog` (prod SMTP later); it never raises into a workflow transition. Thin endpoints on the requests blueprint call the M6 actions then fire notifications. The wizard Review step gains a Submit button.

**Tech Stack:** Flask, Pydantic, React, pytest. Builds on M1–M7.

## Global Constraints
- Inherits all prior constraints. Email is **best-effort** — a send/log failure never blocks the transition (design §9). Submit is **owner-only**.

---

### Task 1: Email/notification adapter

**Files:**
- Create: `backend/app/services/notify.py`
- Test: `backend/tests/test_notify.py`

**Interfaces:** `send_email(recipient, subject, body, request_id=None, type_="INFO")` (best-effort, writes `NotificationLog`); `notify_assignment(req)`, `notify_decision(req, approved)`, `notify_finance_ready(req)`.

- [ ] **Step 1: Failing tests** — `backend/tests/test_notify.py`:
```python
from app.extensions import db
from app.models import NotificationLog
from app.services import notify
from tests.factories import make_user, make_division, make_draft
from app.services.workflow_service import submit, set_thresholds if False else None  # noqa


def test_send_email_logs_notification(app):
    notify.send_email("a@x.com", "Hi", "Body", None, "ASSIGNED")
    row = db.session.query(NotificationLog).one()
    assert row.recipient == "a@x.com" and row.type == "ASSIGNED"


def test_notify_assignment_uses_assignee(app):
    approver = make_user("appr")
    req_owner = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    req = make_draft(req_owner.id, div.id)
    req.assignee_id = approver.id
    db.session.commit()
    notify.notify_assignment(req)
    row = db.session.query(NotificationLog).filter_by(type="ASSIGNED").one()
    assert row.recipient == approver.email
```

- [ ] **Step 2: Run → fail.** `pytest tests/test_notify.py -v`

- [ ] **Step 3: Write** `backend/app/services/notify.py`:
```python
import logging

from app.extensions import db
from app.models import NotificationLog, User

log = logging.getLogger("capex.notify")


def send_email(recipient, subject, body, request_id=None, type_="INFO"):
    """Best-effort notification. Dev driver logs + records NotificationLog.
    Never raises — a failure must not block a workflow transition."""
    try:
        log.info("EMAIL to=%s subject=%s", recipient, subject)
        db.session.add(NotificationLog(request_id=request_id, recipient=recipient, type=type_))
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("notification failed for %s", recipient)


def notify_assignment(req):
    if req.assignee is not None:
        send_email(req.assignee.email, f"{req.number} is waiting for your approval",
                   f"Request {req.number} is assigned to you.", req.id, "ASSIGNED")


def notify_decision(req, approved):
    verb = "approved" if approved else "rejected"
    send_email(req.requestor.email, f"{req.number} was {verb}",
               f"Your request {req.number} was {verb}.", req.id, "DECIDED")


def notify_finance_ready(req):
    users = db.session.query(User).filter(User.active.is_(True)).all()
    for u in users:
        if "FINANCE" in u.roles_list:
            send_email(u.email, f"{req.number} approved — finance section pending",
                       f"Request {req.number} needs the finance cost breakdown.", req.id, "FINANCE_READY")
```

- [ ] **Step 4: Run → pass.** Fix the test import line (remove the stray `noqa` line if it errors) — the real file is:
```python
from app.extensions import db
from app.models import NotificationLog
from app.services import notify
from tests.factories import make_user, make_division, make_draft
```
(Replace the messy import block in Step 1 with these four lines.)

- [ ] **Step 5: Commit** — `git add backend/app/services/notify.py backend/tests/test_notify.py && git commit -m "feat(backend): best-effort email/notification adapter"`

---

### Task 2: Workflow HTTP endpoints + owner-check on submit

**Files:**
- Modify: `backend/app/services/workflow_service.py` (owner check in `submit`)
- Modify: `backend/app/schemas/request.py` (add `FinanceIn`)
- Modify: `backend/app/blueprints/requests.py` (add 5 action endpoints)
- Test: `backend/tests/test_workflow_api.py`

**Interfaces:** `POST /api/requests/<id>/{submit,approve,reject,resubmit,finance}` (login required); each calls the M6 action + notifications; returns `request_out`.

- [ ] **Step 1: Failing tests** — `backend/tests/test_workflow_api.py`:
```python
from app.extensions import db
from app.models import NotificationLog
from tests.factories import make_user, make_division, set_thresholds


def _login(client, user):
    client.post("/api/auth/login", json={"username": user.username, "password": "secret123"})


def _draft_via_api(client):
    return client.post("/api/requests").get_json()["id"]


def test_submit_endpoint_routes_and_notifies(client, app):
    approver = make_user("appr")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    requestor.division_id = div.id
    set_thresholds()
    db.session.commit()
    _login(client, requestor)
    rid = _draft_via_api(client)
    client.patch(f"/api/requests/{rid}", json={
        "equipment_items": [{"units": 1, "condition": "NEW", "type": "T", "make": "M",
                             "model": "Mo", "cost": "30000"}]})
    r = client.post(f"/api/requests/{rid}/submit")
    assert r.status_code == 200
    assert r.get_json()["status"] == "PENDING_L1"
    assert db.session.query(NotificationLog).filter_by(type="ASSIGNED").count() == 1


def test_submit_validation_error(client, app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=make_user("appr").id)
    requestor.division_id = div.id
    set_thresholds()
    db.session.commit()
    _login(client, requestor)
    rid = _draft_via_api(client)  # no equipment
    assert client.post(f"/api/requests/{rid}/submit").status_code == 400


def test_approve_endpoint(client, app):
    approver = make_user("appr")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    requestor.division_id = div.id
    set_thresholds()
    db.session.commit()
    _login(client, requestor)
    rid = _draft_via_api(client)
    client.patch(f"/api/requests/{rid}", json={
        "equipment_items": [{"units": 1, "condition": "NEW", "type": "T", "make": "M",
                             "model": "Mo", "cost": "30000"}]})
    client.post(f"/api/requests/{rid}/submit")
    _login(client, approver)
    r = client.post(f"/api/requests/{rid}/approve", json={})
    assert r.status_code == 200 and r.get_json()["status"] == "APPROVED"


def test_reject_requires_comment_via_api(client, app):
    approver = make_user("appr")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    requestor.division_id = div.id
    set_thresholds()
    db.session.commit()
    _login(client, requestor)
    rid = _draft_via_api(client)
    client.patch(f"/api/requests/{rid}", json={
        "equipment_items": [{"units": 1, "condition": "NEW", "type": "T", "make": "M",
                             "model": "Mo", "cost": "30000"}]})
    client.post(f"/api/requests/{rid}/submit")
    _login(client, approver)
    assert client.post(f"/api/requests/{rid}/reject", json={"comment": ""}).status_code == 400
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3a: Owner check in submit** — in `workflow_service.submit`, after the `DRAFT` check add:
```python
    if req.requestor_id != actor_id:
        raise ServiceError("Only the requestor can submit this request.", 403)
```

- [ ] **Step 3b: FinanceIn schema** — append to `backend/app/schemas/request.py`:
```python
class FinanceIn(BaseModel):
    cost_autos_trucks: Decimal | None = None
    cost_machinery: Decimal | None = None
    cost_improvements: Decimal | None = None
    cost_furniture: Decimal | None = None
    cost_permits: Decimal | None = None
    cost_misc: Decimal | None = None
```

- [ ] **Step 3c: Endpoints** — append to `backend/app/blueprints/requests.py` (add imports `from app.services import workflow_service, notify` and `from app.schemas.request import RequestDraft, FinanceIn`):
```python
@bp.post("/<request_id>/submit")
@login_required
def submit_request(request_id):
    req = workflow_service.submit(request_id, current_user.id)
    notify.notify_assignment(req)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/approve")
@login_required
def approve_request(request_id):
    comment = (request.get_json(silent=True) or {}).get("comment")
    req = workflow_service.approve(request_id, current_user.id, comment)
    if req.status == "APPROVED":
        notify.notify_decision(req, True)
        notify.notify_finance_ready(req)
    else:
        notify.notify_assignment(req)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/reject")
@login_required
def reject_request(request_id):
    comment = (request.get_json(silent=True) or {}).get("comment", "")
    req = workflow_service.reject(request_id, current_user.id, comment)
    notify.notify_decision(req, False)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/resubmit")
@login_required
def resubmit_request(request_id):
    req = workflow_service.resubmit(request_id, current_user.id)
    notify.notify_assignment(req)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/finance")
@login_required
def finance_request(request_id):
    costs = FinanceIn(**(request.get_json(silent=True) or {})).model_dump()
    req = workflow_service.complete_finance(request_id, current_user.id, costs)
    return jsonify(request_service.request_out(req))
```

- [ ] **Step 4: Run → pass.** `pytest tests/test_workflow_api.py tests/test_workflow_submit.py -v` (submit owner check must not break M6 submit tests — they pass the requestor as actor). Then `pytest -q`.

- [ ] **Step 5: Commit** — `git add backend/app/services/workflow_service.py backend/app/schemas/request.py backend/app/blueprints/requests.py backend/tests/test_workflow_api.py && git commit -m "feat(backend): workflow HTTP endpoints (submit/approve/reject/resubmit/finance) + notifications"`

---

### Task 3: Wizard Submit button + smoke

**Files:**
- Modify: `frontend/src/api/requests.ts` (add `submitRequest`)
- Modify: `frontend/src/routes/WizardPage.tsx` (Submit on Review step)

**Interfaces:** `submitRequest(id)`; Review step gets a Submit button that submits and navigates to `/` on success, shows the error otherwise.

- [ ] **Step 1: API** — append to `frontend/src/api/requests.ts`:
```ts
export function submitRequest(id: string): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}/submit`, { method: 'POST' })
}
```

- [ ] **Step 2: Wizard Submit** — in `WizardPage.tsx`:
  - import `useNavigate` from react-router-dom and `submitRequest`, `ApiError`.
  - add inside the component:
```tsx
  const navigate = useNavigate()
  const submit = useMutation({
    mutationFn: () => submitRequest(id),
    onSuccess: () => navigate('/', { replace: true }),
  })
  const submitError = submit.error instanceof ApiError ? submit.error.message : null
```
  - change the `Review` render to pass submit handlers:
```tsx
        {step === 5 && <Review form={form} onSubmit={() => { save.mutate(); submit.mutate() }}
          pending={submit.isPending} error={submitError} />}
```
  - update the `Review` component signature/body:
```tsx
function Review({ form, onSubmit, pending, error }:
  { form: RequestForm; onSubmit: () => void; pending: boolean; error: string | null }) {
  const total = equipmentTotal(form.equipment_items)
  return (
    <div className="space-y-3 text-sm">
      <p><span className="font-medium">Description:</span> {form.description || '—'}</p>
      <p><span className="font-medium">Equipment lines:</span> {form.equipment_items.length}</p>
      <p><span className="font-medium">Total cost:</span> ${total.toLocaleString()}</p>
      {error && <p className="text-red-600" role="alert">{error}</p>}
      <Button disabled={pending} onClick={onSubmit}>Submit for approval</Button>
    </div>
  )
}
```

- [ ] **Step 3: Build** — `./node_modules/.bin/tsc && ./node_modules/.bin/vite build` → no errors.

- [ ] **Step 4: Commit** — `git add frontend/src && git commit -m "feat(frontend): wizard submit-for-approval action"`

- [ ] **Step 5: Smoke (HTTP)** — with backend running, script a full flow with `curl` (or Playwright): as an admin, set division 100's L1 approver and put a requestor in division 100 (via the admin API), log in as the requestor, create a draft, PATCH an equipment line, POST `/submit` → expect `200` `PENDING_L1`; confirm a `NotificationLog` ASSIGNED row exists. (This is also covered by the Task 2 integration tests; the smoke confirms the wired UI path.)

---

## Self-Review
- **Coverage:** notify adapter (§7, best-effort §9) → T1; submit/approve/reject/resubmit/finance endpoints (§6) → T2; wizard Submit (§6 screen 3) → T3. Approve/reject **UI** is M9.
- **Placeholders:** Step 1 of Task 1 contains a deliberately-corrected import (Step 4 gives the clean four-line import) — apply the clean version. No other placeholders.
- **Types:** endpoints return `request_out`; `FinanceIn` fields match `_FINANCE_FIELDS`; `submitRequest` matches the `/submit` route. Submit owner-check keeps M6 submit tests green (actor == requestor there).
