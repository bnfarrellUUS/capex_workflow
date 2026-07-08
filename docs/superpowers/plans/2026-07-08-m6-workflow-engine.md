# M6 — Workflow Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The CAPEX request workflow engine — request-number allocation, request validation schemas, threshold routing, approver resolution (with delegation), and the transactional submit / approve / reject / resubmit / finance-completion actions with an optimistic-concurrency guard — built test-first.

**Architecture:** Pure helpers (`compute_required_levels`, `intended_approver`, `resolve_assignee`) are unit-tested with in-memory objects. Transactional actions in `workflow_service.py` mutate a persisted `CapexRequest`, append an `ApprovalAction` (append-only audit), and guard state transitions with a conditional UPDATE (rowcount check). No HTTP or email yet — those are wired in M8; here everything is exercised directly via pytest.

**Tech Stack:** Python, SQLAlchemy, Pydantic v2, pytest. Builds on M1–M5.

## Global Constraints

- Inherits all prior constraints. Statuses are validated strings: `DRAFT → PENDING_L1 → PENDING_L2 → PENDING_L3 → APPROVED | REJECTED`.
- Action strings: `SUBMITTED | APPROVED | REJECTED | RESUBMITTED | FINANCE_COMPLETED`.
- `total_cost` = sum of equipment line-item costs (each `EquipmentItem.cost` is that line's total). Money is `Decimal`.
- Routing: every request enters at L1 and climbs to the lowest level whose cap covers the total (`max_amount is None` = no limit / top level).
- Delegation: if the intended approver has a delegate, the request is assigned to the delegate; the `ApprovalAction` records `acted_for_id` = the intended approver when the actor differs.
- Concurrency: a state transition guarded on the expected `current_level`; 0 rows updated → `ServiceError("… already actioned …", 409)`.

---

### Task 1: Request-number counter

**Files:**
- Create: `backend/app/services/counter_service.py`
- Test: `backend/tests/test_counter_service.py`

**Interfaces:**
- Produces: `next_request_number() -> str` — allocates the next `CX######` (zero-padded to 6), transactionally, via the `Counter` table (`name="capex_request"`).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_counter_service.py`:
```python
from app.services.counter_service import next_request_number


def test_first_number_is_cx000001(app):
    assert next_request_number() == "CX000001"


def test_numbers_increment(app):
    a = next_request_number()
    b = next_request_number()
    c = next_request_number()
    assert [a, b, c] == ["CX000001", "CX000002", "CX000003"]
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_counter_service.py -v` → FAIL (module missing).

- [ ] **Step 3: Write the service**

`backend/app/services/counter_service.py`:
```python
from app.extensions import db
from app.models import Counter

_COUNTER_NAME = "capex_request"


def next_request_number() -> str:
    counter = db.session.get(Counter, _COUNTER_NAME)
    if counter is None:
        counter = Counter(name=_COUNTER_NAME, value=0)
        db.session.add(counter)
    counter.value += 1
    db.session.commit()
    return f"CX{counter.value:06d}"
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_counter_service.py -v` → both PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/counter_service.py backend/tests/test_counter_service.py
git commit -m "feat(backend): CX request-number counter service"
```

---

### Task 2: Request validation schemas

**Files:**
- Create: `backend/app/schemas/request.py`
- Test: `backend/tests/test_request_schemas.py`

**Interfaces:**
- Produces (consumed by the M7 wizard):
  - `EquipmentItemIn` (units:int, condition:str, type/make/model:str, cost:Decimal).
  - `RequestDraft` — all fields optional (lenient save); `equipment_items: list[EquipmentItemIn] = []`.
  - `RequestSubmit` — strict: requires non-empty `description`, `justification`, `effect_on_operations`, `division_id`, and ≥1 equipment item.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_request_schemas.py`:
```python
import pytest
from pydantic import ValidationError

from app.schemas.request import RequestDraft, RequestSubmit, EquipmentItemIn


def test_draft_allows_empty():
    d = RequestDraft()
    assert d.equipment_items == []
    assert d.description is None


def test_draft_accepts_partial():
    d = RequestDraft(description="Forklift", budgeted=True)
    assert d.description == "Forklift" and d.budgeted is True


def test_submit_requires_core_fields():
    with pytest.raises(ValidationError):
        RequestSubmit(description="x")  # missing the rest


def test_submit_ok_with_all_required():
    s = RequestSubmit(
        description="Forklift", justification="Needed", effect_on_operations="Faster",
        division_id="div1",
        equipment_items=[EquipmentItemIn(units=1, condition="NEW", type="Forklift",
                                         make="Toyota", model="8FGU25", cost="30000")],
    )
    assert s.division_id == "div1"
    assert s.equipment_items[0].cost == 30000
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_request_schemas.py -v` → FAIL (module missing).

- [ ] **Step 3: Write the schemas**

`backend/app/schemas/request.py`:
```python
from decimal import Decimal

from pydantic import BaseModel, Field


class EquipmentItemIn(BaseModel):
    units: int = 1
    condition: str = "NEW"
    type: str = ""
    make: str = ""
    model: str = ""
    cost: Decimal = Decimal(0)


class RequestDraft(BaseModel):
    description: str | None = None
    budgeted: bool | None = None
    replacement: bool | None = None
    health_safety: bool | None = None
    revenue_generating: bool | None = None
    environmental: bool | None = None
    competitive_bids: bool | None = None
    lease_recommended: bool | None = None
    justification: str | None = None
    effect_on_operations: str | None = None
    asset_life: str | None = None
    irr_after_tax: Decimal | None = None
    first_year_ebit: Decimal | None = None
    annual_savings: Decimal | None = None
    payback_years: Decimal | None = None
    npv_savings: Decimal | None = None
    division_id: str | None = None
    equipment_items: list[EquipmentItemIn] = Field(default_factory=list)


class RequestSubmit(BaseModel):
    description: str = Field(min_length=1)
    justification: str = Field(min_length=1)
    effect_on_operations: str = Field(min_length=1)
    division_id: str = Field(min_length=1)
    equipment_items: list[EquipmentItemIn] = Field(min_length=1)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_request_schemas.py -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/request.py backend/tests/test_request_schemas.py
git commit -m "feat(backend): request draft/submit validation schemas"
```

---

### Task 3: Workflow pure helpers + shared test factories

**Files:**
- Create: `backend/app/services/workflow_service.py` (helpers only in this task)
- Create: `backend/tests/factories.py`
- Test: `backend/tests/test_workflow_helpers.py`

**Interfaces:**
- Produces:
  - `compute_required_levels(total_cost, thresholds) -> int`.
  - `intended_approver(level, division, thresholds) -> User | None`.
  - `effective_assignee(user) -> User | None` (delegate if set).
  - `resolve_assignee(level, division, thresholds) -> User | None`.
  - Test factories: `make_user`, `make_division`, `set_thresholds`, `make_draft`.

- [ ] **Step 1: Write shared test factories**

`backend/tests/factories.py`:
```python
from decimal import Decimal

from app.extensions import db
from app.models import User, Division, CapexRequest, EquipmentItem
from app.services import threshold_service
from app.services.security import hash_password


def make_user(username, roles='["APPROVER"]', delegate_id=None):
    u = User(username=username, email=f"{username}@x.com", name=username.title(),
             password_hash=hash_password("secret123"), roles=roles, delegate_id=delegate_id)
    db.session.add(u)
    db.session.commit()
    return u


def make_division(number="100", l1_approver_id=None):
    d = Division(number=number, name="Field Services", l1_approver_id=l1_approver_id)
    db.session.add(d)
    db.session.commit()
    return d


def set_thresholds(l1="50000", l2="250000", l2_approver=None, l3_approver=None):
    rows = {t.level: t for t in threshold_service.list_thresholds()}
    rows[1].max_amount = Decimal(l1)
    rows[2].max_amount = Decimal(l2)
    rows[2].approver_id = l2_approver
    rows[3].max_amount = None
    rows[3].approver_id = l3_approver
    db.session.commit()
    return list(rows.values())


def make_draft(requestor_id, division_id, costs=("30000",), number="CX000001"):
    r = CapexRequest(number=number, requestor_id=requestor_id, division_id=division_id,
                     description="Desc", justification="Just", effect_on_operations="Ops")
    for c in costs:
        r.equipment_items.append(EquipmentItem(units=1, condition="NEW", type="T",
                                               make="M", model="Mo", cost=Decimal(c)))
    db.session.add(r)
    db.session.commit()
    return r
```

- [ ] **Step 2: Write the failing helper tests**

`backend/tests/test_workflow_helpers.py`:
```python
from decimal import Decimal

from app.models import Division, User, ApprovalThreshold
from app.services.workflow_service import (
    compute_required_levels, intended_approver, effective_assignee, resolve_assignee,
)


def _thresholds():
    return [
        ApprovalThreshold(level=1, max_amount=Decimal("50000")),
        ApprovalThreshold(level=2, max_amount=Decimal("250000")),
        ApprovalThreshold(level=3, max_amount=None),
    ]


def test_required_levels_l1():
    assert compute_required_levels(Decimal("30000"), _thresholds()) == 1


def test_required_levels_l2():
    assert compute_required_levels(Decimal("100000"), _thresholds()) == 2


def test_required_levels_l3():
    assert compute_required_levels(Decimal("500000"), _thresholds()) == 3


def test_intended_approver_l1_is_division_approver():
    appr = User(id="a1", username="a", email="a@x", name="A", password_hash="x")
    div = Division(number="100", name="F", l1_approver=appr)
    assert intended_approver(1, div, _thresholds()) is appr


def test_effective_assignee_prefers_delegate():
    delegate = User(id="d1", username="d", email="d@x", name="D", password_hash="x")
    appr = User(id="a1", username="a", email="a@x", name="A", password_hash="x",
                delegate_id="d1", delegate=delegate)
    assert effective_assignee(appr) is delegate


def test_resolve_assignee_l1_with_delegate():
    delegate = User(id="d1", username="d", email="d@x", name="D", password_hash="x")
    appr = User(id="a1", username="a", email="a@x", name="A", password_hash="x",
                delegate_id="d1", delegate=delegate)
    div = Division(number="100", name="F", l1_approver=appr)
    assert resolve_assignee(1, div, _thresholds()) is delegate
```

- [ ] **Step 3: Run to verify fail**

Run: `pytest tests/test_workflow_helpers.py -v` → FAIL (module missing).

- [ ] **Step 4: Write the helpers**

`backend/app/services/workflow_service.py`:
```python
from decimal import Decimal

from sqlalchemy import update as sql_update

from app.extensions import db
from app.models import CapexRequest, ApprovalAction, User
from app.services import threshold_service
from app.services.errors import ServiceError


# ---- pure helpers ----

def compute_required_levels(total_cost, thresholds) -> int:
    for t in sorted(thresholds, key=lambda x: x.level):
        if t.max_amount is None or total_cost <= t.max_amount:
            return t.level
    return max(t.level for t in thresholds)


def intended_approver(level, division, thresholds):
    if level == 1:
        return division.l1_approver if division is not None else None
    match = next((t for t in thresholds if t.level == level), None)
    return match.approver if match is not None else None


def effective_assignee(user):
    if user is None:
        return None
    return user.delegate if user.delegate_id else user


def resolve_assignee(level, division, thresholds):
    return effective_assignee(intended_approver(level, division, thresholds))
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/test_workflow_helpers.py -v` → all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/workflow_service.py backend/tests/factories.py backend/tests/test_workflow_helpers.py
git commit -m "feat(backend): workflow routing/assignment helpers + test factories"
```

---

### Task 4: Submit action

**Files:**
- Modify: `backend/app/services/workflow_service.py` (add `submit` + internals)
- Test: `backend/tests/test_workflow_submit.py`

**Interfaces:**
- Produces: `submit(request_id, actor_id) -> CapexRequest`. Internal helpers `_add_action`, `_open_workflow`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_workflow_submit.py`:
```python
import pytest
from decimal import Decimal

from app.extensions import db
from app.models import ApprovalAction
from app.services.errors import ServiceError
from app.services.workflow_service import submit
from tests.factories import make_user, make_division, set_thresholds, make_draft


def _setup(cost="30000"):
    approver = make_user("appr")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=(cost,))
    return requestor, approver, req


def test_submit_routes_to_l1_and_sets_totals(app):
    requestor, approver, req = _setup(cost="30000")
    result = submit(req.id, requestor.id)
    assert result.status == "PENDING_L1"
    assert result.current_level == 1
    assert result.required_levels == 1
    assert result.total_cost == Decimal("30000")
    assert result.assignee_id == approver.id


def test_submit_large_amount_requires_three_levels(app):
    requestor, approver, req = _setup(cost="500000")
    result = submit(req.id, requestor.id)
    assert result.required_levels == 3
    assert result.status == "PENDING_L1"  # still enters at L1


def test_submit_writes_submitted_action(app):
    requestor, approver, req = _setup()
    submit(req.id, requestor.id)
    actions = db.session.query(ApprovalAction).filter_by(request_id=req.id).all()
    assert len(actions) == 1 and actions[0].action == "SUBMITTED"


def test_submit_requires_equipment(app):
    approver = make_user("appr")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=())
    with pytest.raises(ServiceError):
        submit(req.id, requestor.id)


def test_submit_requires_l1_approver(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=None)
    set_thresholds()
    req = make_draft(requestor.id, div.id)
    with pytest.raises(ServiceError):
        submit(req.id, requestor.id)


def test_submit_only_drafts(app):
    requestor, approver, req = _setup()
    submit(req.id, requestor.id)
    with pytest.raises(ServiceError):
        submit(req.id, requestor.id)  # already PENDING_L1
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_workflow_submit.py -v` → FAIL (`submit` missing).

- [ ] **Step 3: Add submit + internals to workflow_service.py**

Append to `backend/app/services/workflow_service.py`:
```python
# ---- transactional actions ----

def _add_action(req, actor_id, action, level=None, acted_for_id=None, comment=None):
    db.session.add(ApprovalAction(
        request_id=req.id, actor_id=actor_id, action=action,
        level=level, acted_for_id=acted_for_id, comment=comment,
    ))


def _open_workflow(req):
    total = sum((i.cost for i in req.equipment_items), Decimal(0))
    if not req.equipment_items or total <= 0:
        raise ServiceError("Add at least one equipment line item with a cost.")
    if req.division is None:
        raise ServiceError("A division is required.")
    thresholds = threshold_service.list_thresholds()
    l1 = intended_approver(1, req.division, thresholds)
    if l1 is None:
        raise ServiceError("The division has no level-1 approver assigned.")
    req.total_cost = total
    req.required_levels = compute_required_levels(total, thresholds)
    req.current_level = 1
    req.status = "PENDING_L1"
    req.assignee_id = effective_assignee(l1).id


def submit(request_id, actor_id):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if req.status != "DRAFT":
        raise ServiceError("Only drafts can be submitted.")
    _open_workflow(req)
    _add_action(req, actor_id, "SUBMITTED", level=1)
    db.session.commit()
    return req
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_workflow_submit.py -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/workflow_service.py backend/tests/test_workflow_submit.py
git commit -m "feat(backend): workflow submit action (routing + assignment + audit)"
```

---

### Task 5: Approve, reject, and the concurrency guard

**Files:**
- Modify: `backend/app/services/workflow_service.py` (add `approve`, `reject`, `_guarded_transition`)
- Test: `backend/tests/test_workflow_decisions.py`

**Interfaces:**
- Produces: `approve(request_id, actor_id, comment=None)`, `reject(request_id, actor_id, comment)`, `_guarded_transition(request_id, expected_level, values)`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_workflow_decisions.py`:
```python
import pytest
from decimal import Decimal

from app.extensions import db
from app.models import ApprovalAction, CapexRequest
from app.services.errors import ServiceError
from app.services.workflow_service import submit, approve, reject, _guarded_transition
from tests.factories import make_user, make_division, set_thresholds, make_draft


def _two_level():
    l1 = make_user("l1")
    l2 = make_user("l2")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds(l2_approver=l2.id)
    req = make_draft(requestor.id, div.id, costs=("100000",))  # needs L1+L2
    submit(req.id, requestor.id)
    return requestor, l1, l2, req


def test_approve_advances_to_next_level(app):
    requestor, l1, l2, req = _two_level()
    result = approve(req.id, l1.id)
    assert result.status == "PENDING_L2"
    assert result.current_level == 2
    assert result.assignee_id == l2.id


def test_final_approval_marks_approved(app):
    requestor, l1, l2, req = _two_level()
    approve(req.id, l1.id)
    result = approve(req.id, l2.id)
    assert result.status == "APPROVED"
    assert result.assignee_id is None


def test_approve_only_by_assignee(app):
    requestor, l1, l2, req = _two_level()
    with pytest.raises(ServiceError):
        approve(req.id, l2.id)  # l2 is not yet the assignee


def test_reject_requires_comment(app):
    requestor, l1, l2, req = _two_level()
    with pytest.raises(ServiceError):
        reject(req.id, l1.id, "")


def test_reject_sets_status_and_records_comment(app):
    requestor, l1, l2, req = _two_level()
    result = reject(req.id, l1.id, "Not this quarter")
    assert result.status == "REJECTED"
    assert result.assignee_id is None
    action = db.session.query(ApprovalAction).filter_by(request_id=req.id, action="REJECTED").one()
    assert action.comment == "Not this quarter"


def test_guarded_transition_rejects_stale_level(app):
    requestor, l1, l2, req = _two_level()  # current_level == 1
    with pytest.raises(ServiceError):
        _guarded_transition(req.id, 999, {"status": "APPROVED"})
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_workflow_decisions.py -v` → FAIL.

- [ ] **Step 3: Add approve/reject/guard to workflow_service.py**

Append to `backend/app/services/workflow_service.py`:
```python
def _guarded_transition(request_id, expected_level, values):
    stmt = (sql_update(CapexRequest)
            .where(CapexRequest.id == request_id, CapexRequest.current_level == expected_level)
            .values(**values))
    result = db.session.execute(stmt)
    if result.rowcount != 1:
        raise ServiceError("This request was already actioned by someone else.", 409)


def _require_assignee(req, actor_id):
    if not req.status.startswith("PENDING_L"):
        raise ServiceError("This request is not awaiting a decision.")
    if req.assignee_id != actor_id:
        raise ServiceError("This request is not assigned to you.", 403)


def _acted_for(req, level, actor_id, thresholds):
    intended = intended_approver(level, req.division, thresholds)
    if intended is not None and intended.id != actor_id:
        return intended.id
    return None


def approve(request_id, actor_id, comment=None):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    _require_assignee(req, actor_id)
    thresholds = threshold_service.list_thresholds()
    level = req.current_level
    acted_for = _acted_for(req, level, actor_id, thresholds)

    if level >= req.required_levels:
        values = {"status": "APPROVED", "assignee_id": None}
    else:
        nxt = level + 1
        assignee = resolve_assignee(nxt, req.division, thresholds)
        if assignee is None:
            raise ServiceError(f"No approver configured for level {nxt}.")
        values = {"status": f"PENDING_L{nxt}", "current_level": nxt, "assignee_id": assignee.id}

    _guarded_transition(req.id, level, values)
    _add_action(req, actor_id, "APPROVED", level=level, acted_for_id=acted_for, comment=comment)
    db.session.commit()
    db.session.refresh(req)
    return req


def reject(request_id, actor_id, comment):
    if not comment or not comment.strip():
        raise ServiceError("A comment is required to reject a request.")
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    _require_assignee(req, actor_id)
    thresholds = threshold_service.list_thresholds()
    level = req.current_level
    acted_for = _acted_for(req, level, actor_id, thresholds)
    _guarded_transition(req.id, level, {"status": "REJECTED", "assignee_id": None})
    _add_action(req, actor_id, "REJECTED", level=level, acted_for_id=acted_for, comment=comment)
    db.session.commit()
    db.session.refresh(req)
    return req
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_workflow_decisions.py -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/workflow_service.py backend/tests/test_workflow_decisions.py
git commit -m "feat(backend): workflow approve/reject with optimistic-concurrency guard"
```

---

### Task 6: Resubmit and finance-completion

**Files:**
- Modify: `backend/app/services/workflow_service.py` (add `resubmit`, `complete_finance`)
- Test: `backend/tests/test_workflow_resubmit_finance.py`

**Interfaces:**
- Produces: `resubmit(request_id, actor_id)`, `complete_finance(request_id, actor_id, costs: dict)`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_workflow_resubmit_finance.py`:
```python
import pytest
from decimal import Decimal

from app.extensions import db
from app.models import ApprovalAction, CapexRequest
from app.services.errors import ServiceError
from app.services.workflow_service import submit, approve, reject, resubmit, complete_finance
from tests.factories import make_user, make_division, set_thresholds, make_draft


def _rejected():
    l1 = make_user("l1")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)
    reject(req.id, l1.id, "Fix the quote")
    return requestor, l1, req


def test_resubmit_restarts_at_l1_and_preserves_history(app):
    requestor, l1, req = _rejected()
    result = resubmit(req.id, requestor.id)
    assert result.status == "PENDING_L1"
    assert result.current_level == 1
    actions = [a.action for a in db.session.query(ApprovalAction).filter_by(request_id=req.id).all()]
    assert "SUBMITTED" in actions and "REJECTED" in actions and "RESUBMITTED" in actions


def test_resubmit_only_by_requestor(app):
    requestor, l1, req = _rejected()
    with pytest.raises(ServiceError):
        resubmit(req.id, l1.id)


def test_resubmit_only_when_rejected(app):
    l1 = make_user("l1")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id)
    submit(req.id, requestor.id)  # PENDING_L1, not rejected
    with pytest.raises(ServiceError):
        resubmit(req.id, requestor.id)


def _approved_request():
    l1 = make_user("l1")
    requestor = make_user("req", roles='["REQUESTOR"]')
    finance = make_user("fin", roles='["FINANCE"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)
    approve(req.id, l1.id)  # required_levels==1 -> APPROVED
    return requestor, l1, finance, req


def test_complete_finance_sets_costs(app):
    requestor, l1, finance, req = _approved_request()
    result = complete_finance(req.id, finance.id, {
        "cost_machinery": Decimal("30000"),
    })
    assert result.finance_completed is True
    assert result.cost_machinery == Decimal("30000")
    action = db.session.query(ApprovalAction).filter_by(request_id=req.id, action="FINANCE_COMPLETED").one()
    assert action is not None


def test_complete_finance_requires_finance_role(app):
    requestor, l1, finance, req = _approved_request()
    with pytest.raises(ServiceError):
        complete_finance(req.id, l1.id, {})  # l1 is not finance


def test_complete_finance_requires_approved(app):
    l1 = make_user("l1")
    requestor = make_user("req", roles='["REQUESTOR"]')
    finance = make_user("fin", roles='["FINANCE"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id)
    submit(req.id, requestor.id)  # PENDING_L1, not approved
    with pytest.raises(ServiceError):
        complete_finance(req.id, finance.id, {})
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_workflow_resubmit_finance.py -v` → FAIL.

- [ ] **Step 3: Add resubmit + complete_finance to workflow_service.py**

Append to `backend/app/services/workflow_service.py`:
```python
_FINANCE_FIELDS = (
    "cost_autos_trucks", "cost_machinery", "cost_improvements",
    "cost_furniture", "cost_permits", "cost_misc",
)


def resubmit(request_id, actor_id):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if req.status != "REJECTED":
        raise ServiceError("Only rejected requests can be resubmitted.")
    if req.requestor_id != actor_id:
        raise ServiceError("Only the requestor can resubmit.", 403)
    _open_workflow(req)
    _add_action(req, actor_id, "RESUBMITTED", level=1)
    db.session.commit()
    return req


def complete_finance(request_id, actor_id, costs):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    actor = db.session.get(User, actor_id)
    if actor is None or "FINANCE" not in actor.roles_list:
        raise ServiceError("The Finance role is required.", 403)
    if req.status != "APPROVED":
        raise ServiceError("Only approved requests can be completed by Finance.")
    if req.finance_completed:
        raise ServiceError("The Finance section is already completed.")
    for field in _FINANCE_FIELDS:
        setattr(req, field, costs.get(field))
    req.finance_completed = True
    _add_action(req, actor_id, "FINANCE_COMPLETED")
    db.session.commit()
    return req
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_workflow_resubmit_finance.py -v` → all PASS.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q` → all backend tests pass (M1–M6).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/workflow_service.py backend/tests/test_workflow_resubmit_finance.py
git commit -m "feat(backend): workflow resubmit + finance-completion actions"
```

---

## Self-Review

**Spec coverage (spec §5 workflow rules, §9 concurrency, §10 test-first engine, §14 M6 slice):**
- CX number allocation → Task 1. ✓
- Draft-lenient / submit-strict validation schemas → Task 2. ✓
- Threshold routing + approver resolution + delegation → Task 3. ✓
- Submit (totals, required levels, L1 assignment, audit) → Task 4. ✓
- Approve (level advancement → APPROVED), reject (comment required), concurrency guard → Task 5. ✓
- Resubmit (restart at L1, history preserved), finance-completion (role + status gated) → Task 6. ✓
- No HTTP/email here — the submit/approve/… endpoints and notifications are M8.

**Placeholder scan:** No TBD/TODO; every step has complete code + expected result. ✓

**Type consistency:** `intended_approver`/`resolve_assignee`/`effective_assignee` signatures consistent across helper tests and the actions. `_open_workflow` reused by `submit` and `resubmit`. `_guarded_transition(request_id, expected_level, values)` matches its test. Action strings (`SUBMITTED/APPROVED/REJECTED/RESUBMITTED/FINANCE_COMPLETED`) and statuses (`PENDING_L{n}/APPROVED/REJECTED`) consistent. `_FINANCE_FIELDS` matches the `CapexRequest` finance columns from M1. ✓
