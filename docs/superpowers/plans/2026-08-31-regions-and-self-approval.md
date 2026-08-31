# Regions, Region-VP L2 Routing & Self-Approval Prevention — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Region entity (~5 regions grouping the 25–30 divisions), route Level-2 approval to the request's region's VP pool, and prevent anyone from approving their own request (excluded from every pool; empty levels are skipped upward).

**Architecture:** `Region` mirrors how `Division` carries `l1_approvers` — a `vp_approvers` many-to-many. `Division.region_id` (nullable column, required in the form) links them. `workflow_service.intended_approvers` sources level 2 from `division.region.vp_approvers`; `eligible_actors` gains an `exclude_id` (the requestor) applied to both the configured approver and the delegate-resolved actor; a new `next_pending_level` helper skips levels with no eligible actor (uniformly — emptied by exclusion or simply unconfigured), so a request always lands with a real second person, escalating past `required_levels` when needed. One approval at a level ≥ `required_levels` approves the request.

**Tech Stack:** Flask + SQLAlchemy 2.0 (typed `Mapped`) + Alembic + Pydantic v2; React 19 + TS + TanStack Query 5 + Tailwind v4.

**Spec:** `docs/superpowers/specs/2026-08-31-regions-and-self-approval-design.md`

## Global Constraints

- Backend tests: `cd backend && .venv/Scripts/python -m pytest -q` (venv already exists; on this machine plain `pytest` may not be the venv one).
- Frontend commands run via node to dodge the `&` in the repo path: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `node ./node_modules/vitest/vitest.mjs run`, `node ./node_modules/vite/bin/vite.js build` (from `frontend/`).
- Keep routes thin; logic in `services/`; raise `ServiceError(msg, status)`.
- Money columns use the `MONEY` (`Numeric(18,2)`) constant; ids are `String(36)` uuid hex via the models' `_id` default.
- Commit after every task; commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- One deviation from the spec, decided during planning: the regions GET endpoint is **ADMIN-only** (the spec guessed "any signed-in user", but only admin pages consume it, and the divisions GET it mirrors is already ADMIN-only).

---

### Task 1: Region model, `Division.region_id`, migration

**Files:**
- Modify: `backend/app/models/__init__.py` (association tables block ~line 15; `Division` class ~line 88)
- Create: `backend/migrations/versions/<newrev>_regions.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `Region` model (`id`, `name`, `active`, `vp_approvers: list[User]`), `region_vp_approvers` table, `Division.region_id`/`Division.region`. Later tasks import `Region` from `app.models`.

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_models.py`:

```python
def test_region_links_divisions_and_vps(app):
    from app.models import Region, Division, User
    from app.extensions import db
    vp = User(email="vp@x.com", name="VP", password_hash="x")
    region = Region(name="West", vp_approvers=[vp])
    div = Division(number="900", name="Yard", region=region)
    db.session.add_all([vp, region, div])
    db.session.commit()
    assert div.region.name == "West"
    assert [u.email for u in div.region.vp_approvers] == ["vp@x.com"]
    assert region.active is True
```

(Match the existing test file's fixture style — if its tests take `app`, use `app`.)

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'Region'`

- [ ] **Step 3: Implement the model.** In `backend/app/models/__init__.py`, next to `division_l1_approvers`/`threshold_approvers`:

```python
region_vp_approvers = Table(
    "region_vp_approvers", db.metadata,
    Column("region_id", String(36), ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id", ondelete="NO ACTION"), primary_key=True),
)
```

New class placed just above `Division`:

```python
class Region(db.Model):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Level-2 approvers (the region's VP + backups; any one may approve).
    vp_approvers: Mapped[list["User"]] = relationship("User", secondary=region_vp_approvers)

    divisions: Mapped[list["Division"]] = relationship(back_populates="region")
```

On `Division`, after `l1_approvers`:

```python
    # Nullable because divisions predate regions; the admin form requires it.
    region_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("regions.id", ondelete="NO ACTION"), nullable=True
    )
    region: Mapped[Optional["Region"]] = relationship(back_populates="divisions")
```

Also update the comment at the association-table block: L2 approvers are per-region now.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_models.py -q` → PASS

- [ ] **Step 5: Write the migration.** Find the current head: `cd backend && .venv/Scripts/python -m flask db heads`. Create `backend/migrations/versions/d4e5f6a7b8c9_regions.py` (style-match `b2c3d4e5f6a7_budget_amount.py`):

```python
"""regions + division.region_id

Revision ID: d4e5f6a7b8c9
Revises: <current head>
Create Date: 2026-08-31
"""
import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "<current head>"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "regions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "region_vp_approvers",
        sa.Column("region_id", sa.String(36), sa.ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="NO ACTION"), primary_key=True),
    )
    with op.batch_alter_table("divisions") as batch:
        batch.add_column(sa.Column("region_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_divisions_region", "regions", ["region_id"], ["id"])


def downgrade():
    with op.batch_alter_table("divisions") as batch:
        batch.drop_constraint("fk_divisions_region", type_="foreignkey")
        batch.drop_column("region_id")
    op.drop_table("region_vp_approvers")
    op.drop_table("regions")
```

- [ ] **Step 6: Apply and verify**

Run: `cd backend && .venv/Scripts/python -m flask db upgrade` → succeeds; `.venv/Scripts/python -m pytest -q` → full suite still green (tests use `create_all`, but run it anyway).

- [ ] **Step 7: Commit** — `feat(model): Region entity with VP approver pool; divisions get region_id`

---

### Task 2: Regions API + region on the divisions API

**Files:**
- Create: `backend/app/schemas/region.py`, `backend/app/services/region_service.py`, `backend/app/blueprints/regions.py`
- Modify: `backend/app/__init__.py` (blueprint registration block, ~line 45–75), `backend/app/schemas/division.py`, `backend/app/services/division_service.py`, `backend/app/blueprints/divisions.py`
- Test: create `backend/tests/test_regions_api.py`; modify `backend/tests/test_divisions_api.py`

**Interfaces:**
- Consumes: `Region` model from Task 1.
- Produces: `GET/POST /api/regions`, `PATCH /api/regions/<id>` (all ADMIN-only). `region_out(r)` → `{id, name, active, vp_approver_ids, vp_approver_names, division_count}`. `division_out` gains `region_id`, `region_name`. `DivisionCreate`/`DivisionUpdate` gain `region_id: str | None = None`; `division_service.create_division`/`update_division` accept `region_id` and 400 on an unknown id.

- [ ] **Step 1: Write failing API tests.** `backend/tests/test_regions_api.py`, mirroring the login/auth helper pattern used in `backend/tests/test_divisions_api.py` (read it first and copy its client-login helper verbatim). Cover:

```python
# - GET /api/regions requires ADMIN (a REQUESTOR-only user gets 403)
# - POST /api/regions {"name": "West"} → 201, echoes id/name/active=True/empty vp lists
# - POST duplicate name → 409
# - PATCH /api/regions/<id> {"name": "West", "active": false,
#     "vp_approver_ids": [vp.id]} → vp_approver_ids/names echo back
# - PATCH unknown id → 404
```

Also in `test_divisions_api.py`: updating a division with `region_id` of a created region echoes `region_id` and `region_name`; `region_id: "nope"` → 400.

- [ ] **Step 2: Run to verify failure** — `pytest tests/test_regions_api.py tests/test_divisions_api.py -q` → FAIL (404s: blueprint missing).

- [ ] **Step 3: Implement.**

`backend/app/schemas/region.py`:

```python
from pydantic import BaseModel, Field


class RegionCreate(BaseModel):
    name: str = Field(min_length=1)


class RegionUpdate(BaseModel):
    name: str = Field(min_length=1)
    active: bool = True
    vp_approver_ids: list[str] = []
```

`backend/app/services/region_service.py` (clone the shape of `division_service.py`):

```python
from app.extensions import db
from app.models import Region, User
from app.services.errors import ServiceError


def _users(ids):
    ids = [i for i in (ids or []) if i]
    return db.session.query(User).filter(User.id.in_(ids)).all() if ids else []


def list_regions():
    return db.session.query(Region).order_by(Region.name).all()


def create_region(*, name):
    nm = name.strip()
    if db.session.query(Region).filter_by(name=nm).first() is not None:
        raise ServiceError("Region name already exists.", 409)
    region = Region(name=nm)
    db.session.add(region)
    db.session.commit()
    return region


def update_region(region_id, *, name, active, vp_approver_ids):
    region = db.session.get(Region, region_id)
    if region is None:
        raise ServiceError("Region not found.", 404)
    nm = name.strip()
    clash = db.session.query(Region).filter(
        Region.name == nm, Region.id != region_id).first()
    if clash is not None:
        raise ServiceError("Region name already exists.", 409)
    region.name = nm
    region.active = active
    region.vp_approvers = _users(vp_approver_ids)
    db.session.commit()
    return region
```

`backend/app/blueprints/regions.py` (clone `divisions.py`):

```python
from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.region import RegionCreate, RegionUpdate
from app.services import region_service

bp = Blueprint("regions", __name__, url_prefix="/api/regions")


def region_out(r):
    return {
        "id": r.id, "name": r.name, "active": r.active,
        "vp_approver_ids": [u.id for u in r.vp_approvers],
        "vp_approver_names": [u.name for u in r.vp_approvers],
        "division_count": len(r.divisions),
    }


@bp.get("")
@require_roles("ADMIN")
def list_regions():
    return jsonify([region_out(r) for r in region_service.list_regions()])


@bp.post("")
@require_roles("ADMIN")
def create_region():
    data = RegionCreate(**(request.get_json(silent=True) or {}))
    region = region_service.create_region(**data.model_dump())
    return jsonify(region_out(region)), 201


@bp.patch("/<region_id>")
@require_roles("ADMIN")
def update_region(region_id):
    data = RegionUpdate(**(request.get_json(silent=True) or {}))
    region = region_service.update_region(region_id, **data.model_dump())
    return jsonify(region_out(region))
```

Register in `backend/app/__init__.py` next to the divisions blueprint:

```python
    from .blueprints.regions import bp as regions_bp
    app.register_blueprint(regions_bp)
```

Divisions: add `region_id: str | None = None` to **both** `DivisionCreate` and `DivisionUpdate`. In `division_service`, add a resolver and use it in both mutators:

```python
def _region(region_id):
    if not region_id:
        return None
    from app.models import Region
    region = db.session.get(Region, region_id)
    if region is None:
        raise ServiceError("Region not found.", 400)
    return region
```

`create_division(*, number, name, region_id=None)` sets `div.region = _region(region_id)`; `update_division(..., region_id)` sets `div.region = _region(region_id)`. In `division_out` add:

```python
        "region_id": d.region_id,
        "region_name": d.region.name if d.region else None,
```

- [ ] **Step 4: Run tests** — `pytest tests/test_regions_api.py tests/test_divisions_api.py -q` → PASS; then full `pytest -q`.

- [ ] **Step 5: Commit** — `feat(api): /api/regions CRUD; divisions carry region_id`

---

### Task 3: Workflow pure helpers — region L2, requestor exclusion, level skipping

**Files:**
- Modify: `backend/app/services/workflow_service.py:20-48` (pure helpers section only)
- Test: `backend/tests/test_workflow_helpers.py`

**Interfaces:**
- Consumes: `Region` model.
- Produces (exact signatures later tasks rely on):
  - `intended_approvers(level, division, thresholds)` — level 2 now reads `division.region.vp_approvers`.
  - `eligible_actors(level, division, thresholds, exclude_id=None)`
  - `first_assignee(level, division, thresholds, exclude_id=None)`
  - `next_pending_level(after_level, division, thresholds, exclude_id=None) -> int | None`

- [ ] **Step 1: Write failing unit tests** appended to `test_workflow_helpers.py` (in-memory objects, no DB — match the file's existing style):

```python
def test_intended_approvers_l2_come_from_region():
    from app.models import Region
    vp = User(id="vp", email="vp@x", name="VP", password_hash="x")
    div = Division(number="100", name="F", region=Region(name="West", vp_approvers=[vp]))
    assert intended_approvers(2, div, _thresholds()) == [vp]


def test_intended_approvers_l2_empty_without_region():
    div = Division(number="100", name="F")
    assert intended_approvers(2, div, _thresholds()) == []


def test_eligible_actors_exclude_requestor_directly():
    a1 = User(id="a1", email="a@x", name="A", password_hash="x")
    rq = User(id="rq", email="r@x", name="R", password_hash="x")
    div = Division(number="100", name="F", l1_approvers=[a1, rq])
    assert eligible_actors(1, div, _thresholds(), exclude_id="rq") == [a1]


def test_eligible_actors_exclude_requestor_as_delegate():
    rq = User(id="rq", email="r@x", name="R", password_hash="x")
    appr = User(id="a1", email="a@x", name="A", password_hash="x",
                delegate_id="rq", delegate=rq)
    div = Division(number="100", name="F", l1_approvers=[appr])
    assert eligible_actors(1, div, _thresholds(), exclude_id="rq") == []


def test_next_pending_level_skips_empty_levels():
    from app.models import Region
    vp = User(id="vp", email="vp@x", name="VP", password_hash="x")
    div = Division(number="100", name="F", l1_approvers=[],
                   region=Region(name="West", vp_approvers=[vp]))
    from app.services.workflow_service import next_pending_level
    assert next_pending_level(0, div, _thresholds()) == 2
    assert next_pending_level(2, div, _thresholds()) is None


def test_next_pending_level_none_when_requestor_is_everyone():
    rq = User(id="rq", email="r@x", name="R", password_hash="x")
    div = Division(number="100", name="F", l1_approvers=[rq])
    from app.services.workflow_service import next_pending_level
    assert next_pending_level(0, div, _thresholds(), exclude_id="rq") is None
```

- [ ] **Step 2: Verify failure** — `pytest tests/test_workflow_helpers.py -q` → FAIL.

- [ ] **Step 3: Implement** in `workflow_service.py`:

```python
def intended_approvers(level, division, thresholds):
    """The users configured to approve at a level (any one of them may act)."""
    if level == 1:
        return list(division.l1_approvers) if division is not None else []
    if level == 2:
        region = division.region if division is not None else None
        return list(region.vp_approvers) if region is not None else []
    match = next((t for t in thresholds if t.level == level), None)
    return list(match.approvers) if match is not None else []


def eligible_actors(level, division, thresholds, exclude_id=None):
    """Who may actually act at a level: each configured approver mapped through
    their out-of-office delegate, de-duplicated. `exclude_id` (the requestor)
    is barred in any capacity — as a configured approver or as the delegate
    who would act for one."""
    seen, out = set(), []
    for approver in intended_approvers(level, division, thresholds):
        if exclude_id is not None and approver.id == exclude_id:
            continue
        actor = effective_assignee(approver)
        if actor is None or actor.id in seen:
            continue
        if exclude_id is not None and actor.id == exclude_id:
            continue
        seen.add(actor.id)
        out.append(actor)
    return out


def first_assignee(level, division, thresholds, exclude_id=None):
    actors = eligible_actors(level, division, thresholds, exclude_id=exclude_id)
    return actors[0] if actors else None


def next_pending_level(after_level, division, thresholds, exclude_id=None):
    """The lowest level above `after_level` where someone may act; empty
    levels — unconfigured, or emptied by the requestor exclusion — are
    skipped uniformly. None when nobody is left."""
    for level in (1, 2, 3):
        if level > after_level and eligible_actors(
                level, division, thresholds, exclude_id=exclude_id):
            return level
    return None
```

- [ ] **Step 4: Run** `pytest tests/test_workflow_helpers.py -q` → PASS. Full suite must also still pass (`exclude_id` defaults keep old callers working): `pytest -q`.

- [ ] **Step 5: Commit** — `feat(workflow): region-sourced L2 pool, requestor exclusion, level skipping helpers`

---

### Task 4: Wire the transactional workflow + migrate test factories

**Files:**
- Modify: `backend/app/services/workflow_service.py` (`_open_workflow`, `approve`, `_require_current_approver`, `_acted_for`), `backend/tests/factories.py`
- Test: create `backend/tests/test_workflow_self_approval.py`; adjust existing workflow tests where error-message/routing assumptions change

**Interfaces:**
- Consumes: Task 3 helpers.
- Produces: submit/resubmit open at `next_pending_level(0, ...)`; approve advances via `next_pending_level(level, ...)`; APPROVED when the acting level ≥ `required_levels`. Factories: `make_region(name="Test Region", vp_ids=None)`; `make_division(..., region=None)` attaches the shared default region when one exists; `set_thresholds` keeps its signature but routes `l2_approver`/`l2_approvers` into the shared default region.

- [ ] **Step 1: Update factories first** (they are test plumbing, not behavior under test). In `backend/tests/factories.py`:

```python
from app.models import User, Division, Region, CapexRequest, EquipmentItem

_DEFAULT_REGION_NAME = "Test Region"


def _default_region():
    return db.session.query(Region).filter_by(name=_DEFAULT_REGION_NAME).one_or_none()


def make_region(name=_DEFAULT_REGION_NAME, vp_ids=None):
    r = Region(name=name)
    r.vp_approvers = _users(vp_ids or [])
    db.session.add(r)
    db.session.commit()
    return r


def make_division(number="100", l1_approver_id=None, l1_approver_ids=None, region=None):
    d = Division(number=number, name="Field Services")
    d.l1_approvers = _users(l1_approver_ids if l1_approver_ids is not None else [l1_approver_id])
    d.region = region if region is not None else _default_region()
    db.session.add(d)
    db.session.commit()
    return d


def set_thresholds(l1="50000", l2="250000", l2_approver=None, l3_approver=None,
                   l2_approvers=None, l3_approvers=None):
    rows = {t.level: t for t in threshold_service.list_thresholds()}
    rows[1].max_amount = Decimal(l1)
    rows[2].max_amount = Decimal(l2)
    # L2 approvers live on a region now. Keep this factory's signature: route
    # the given users into a shared default region and attach it to every
    # division that doesn't have one yet (make_division picks it up too, so
    # either call order works).
    region = _default_region() or Region(name=_DEFAULT_REGION_NAME)
    region.vp_approvers = _users(l2_approvers if l2_approvers is not None else [l2_approver])
    db.session.add(region)
    for d in db.session.query(Division).all():
        if d.region_id is None:
            d.region = region
    rows[3].max_amount = None
    rows[3].approvers = _users(l3_approvers if l3_approvers is not None else [l3_approver])
    db.session.commit()
    return list(rows.values())
```

(`rows[2].approvers` is deliberately no longer set — nothing reads it.)

- [ ] **Step 2: Write failing behavior tests**, `backend/tests/test_workflow_self_approval.py`. Look at `test_workflow_submit.py`/`test_workflow_decisions.py` first and reuse their setup idioms (factories + `workflow_service.submit/approve`). Cover, as separate tests:

```python
# 1. L2 routes to the region VP: requestor + l1 approver + region VP via
#    make_region(vp_ids=[vp.id]) + make_division(region=...), cost above L1 cap;
#    submit → PENDING_L1; approve as l1 → PENDING_L2, assignee == vp,
#    vp id in eligible ids. Put users the threshold-L2 row would have had
#    NOWHERE — the point is the pool comes from the region.
# 2. Requestor in the L1 pool alongside another approver: submit → the other
#    approver may approve; workflow_service.approve(req.id, requestor.id)
#    raises ServiceError 403 ("not assigned to you").
# 3. Requestor is the SOLE L1 approver, small request (needs L1 only), region
#    VP exists: submit → status PENDING_L2, current_level == 2; VP approves →
#    APPROVED (level 2 >= required_levels 1, single approval suffices).
# 4. Requestor is sole approver at EVERY level (sole L1, sole region VP, sole
#    L3): submit raises ServiceError mentioning "cannot approve their own".
# 5. Requestor is an approver's delegate: approver A has delegate == requestor;
#    another L1 approver B exists. Eligible actors exclude the requestor;
#    approve(req.id, requestor.id) → 403; approve(req.id, B.id) works.
# 6. Skip an empty middle level: division has region with NO VPs, cost needs
#    L3; L1 approves → status jumps to PENDING_L3 (level 2 skipped).
```

- [ ] **Step 3: Verify the new tests fail** — `pytest tests/test_workflow_self_approval.py -q` (failures expected on routing/exclusion, not setup errors).

- [ ] **Step 4: Implement** in `workflow_service.py`:

`_open_workflow` — replace the L1-specific block:

```python
    thresholds = threshold_service.list_thresholds()
    first = next_pending_level(0, req.division, thresholds, exclude_id=req.requestor_id)
    if first is None:
        raise ServiceError(
            "No eligible approver was found at any level — requestors cannot "
            "approve their own requests. Check the division's level-1 approvers, "
            "the region's VP list, and the level-3 approvers.")
    req.total_cost = total
    req.required_levels = compute_required_levels(total, thresholds)
    req.current_level = first
    req.status = f"PENDING_L{first}"
    req.assignee_id = first_assignee(
        first, req.division, thresholds, exclude_id=req.requestor_id).id
```

`submit`/`resubmit` log their action at the actual opening level: change `_add_action(req, actor_id, "SUBMITTED", level=1)` to `level=req.current_level` (same in `resubmit`).

`_require_current_approver`:

```python
    actor_ids = {u.id for u in eligible_actors(
        req.current_level, req.division, thresholds, exclude_id=req.requestor_id)}
```

`_acted_for` — skip the requestor as a principal:

```python
    for approver in intended_approvers(level, req.division, thresholds):
        if approver.id == req.requestor_id:
            continue
        ...
```

`approve` — replace the advance branch:

```python
    if level >= req.required_levels:
        values = {"status": "APPROVED", "assignee_id": None}
    else:
        nxt = next_pending_level(level, req.division, thresholds,
                                 exclude_id=req.requestor_id)
        if nxt is None:
            raise ServiceError(
                "No eligible approver is configured above this level.")
        assignee = first_assignee(nxt, req.division, thresholds,
                                  exclude_id=req.requestor_id)
        values = {"status": f"PENDING_L{nxt}", "current_level": nxt,
                  "assignee_id": assignee.id}
```

- [ ] **Step 5: Run the new file, then the whole suite** — `pytest tests/test_workflow_self_approval.py -q` → PASS; `pytest -q` → fix stragglers. Expected breakage classes (fix the tests, not the behavior): assertions on the old "The division has no level-1 approver assigned." message (now the generic no-eligible-approver message); tests where the requestor doubled as an approver (now excluded — give them a distinct approver user); any test asserting `rows[2].approvers` routing. Do NOT weaken the concurrency guard or delegate tests to get green.

- [ ] **Step 6: Commit** — `feat(workflow): route L2 via region VP, block self-approval, skip empty levels`

---

### Task 5: Requestor exclusion in worklists, visibility, serializer, notifications

**Files:**
- Modify: `backend/app/services/request_service.py:22-59` (`_can_view`, `list_requests`) and `:133-146` (`request_out`), `backend/app/services/notify.py:57-66` (`notify_assignment`) and `:89-103` (`notify_comment`)
- Test: `backend/tests/test_request_list.py`, `backend/tests/test_notify.py`

**Interfaces:**
- Consumes: `eligible_actors(..., exclude_id=...)` from Task 3.
- Produces: every `eligible_actors` call site in `request_service`/`notify` passes `exclude_id=req.requestor_id` (or `r.requestor_id`), so the requestor never appears in `current_approver_ids`, on their own "assigned" worklist, or on assignment/comment recipient lists.

- [ ] **Step 1: Write failing tests.**

In `test_request_list.py` (reuse its setup idioms): a user who is both an L1 approver and the requestor of request X, plus an approver of someone else's request Y at the current level → `list_requests(viewer, scope="assigned")` contains Y but NOT X.

In `test_notify.py` (reuse its spy pattern — any spy on `email_outlook.send` must accept `attachments=`): a pending request whose requestor also sits in the current level's pool → `notify_assignment` sends to the other approver(s) only, never the requestor's email.

- [ ] **Step 2: Verify failure** — `pytest tests/test_request_list.py tests/test_notify.py -q`.

- [ ] **Step 3: Implement.** All four call sites gain the keyword:

- `request_service._can_view`: `eligible_actors(req.current_level, req.division, ..., exclude_id=req.requestor_id)` (the requestor already passed the `viewer.id == req.requestor_id` check above; this just stops pool-membership from being the reason).
- `request_service.list_requests` assigned scope: `exclude_id=r.requestor_id` inside the comprehension.
- `request_service.request_out`: `exclude_id=req.requestor_id` so `current_approver_ids`/`names` don't display the requestor.
- `notify.notify_assignment`: `exclude_id=req.requestor_id`.
- `notify.notify_comment` (requestor-authored branch): `exclude_id=req.requestor_id`.

- [ ] **Step 4: Run** the two files, then `pytest -q` → all green.

- [ ] **Step 5: Commit** — `feat(requests): exclude the requestor from pools in worklists, serializer, and notifications`

---

### Task 6: Seed data

**Files:**
- Modify: `backend/seed.py`
- Test: `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: `Region` model.
- Produces: a fresh dev DB has a "Central" region (admin as its VP, so L2 is exercisable immediately) attached to both seeded divisions.

- [ ] **Step 1: Extend the seed test** (read `test_seed.py` first; add asserts): after `seed(session)`, a Region named "Central" exists, `admin@uniteduptime.com` is in its `vp_approvers`, and both divisions `100`/`200` have `region_id` set to it.

- [ ] **Step 2: Verify failure** — `pytest tests/test_seed.py -q`.

- [ ] **Step 3: Implement** in `seed.py` (after the divisions, before commit):

```python
    admin = session.query(User).filter_by(email="admin@uniteduptime.com").one()
    region = _get_or_create(session, Region, name="Central")
    if admin not in region.vp_approvers:
        region.vp_approvers.append(admin)
    for number in ("100", "200"):
        div = session.query(Division).filter_by(number=number).one()
        if div.region_id is None:
            div.region = region
```

Import `Region` at the top. Keep `_get_or_create` usage consistent.

- [ ] **Step 4: Run** — `pytest tests/test_seed.py -q` → PASS; also run `.venv/Scripts/python seed.py` against the dev DB (idempotent).

- [ ] **Step 5: Commit** — `feat(seed): Central region with admin as VP, attached to seeded divisions`

---

### Task 7: Frontend — Regions admin section

**Files:**
- Create: `frontend/src/api/regions.ts`, `frontend/src/routes/admin/RegionsPage.tsx`, `frontend/src/routes/admin/RegionNewPage.tsx`, `frontend/src/routes/admin/RegionEditPage.tsx`, `frontend/src/routes/admin/RegionForm.tsx`
- Modify: `frontend/src/components/NavIcons.tsx`, `frontend/src/components/ui/BrandCard.tsx`, `frontend/src/components/ui/BrandCard.test.tsx`, `frontend/src/components/AppShell.tsx`, `frontend/src/App.tsx`
- Test: `frontend/src/components/ui/BrandCard.test.tsx` (mark list)

**Interfaces:**
- Consumes: `/api/regions` from Task 2.
- Produces: `Region`/`RegionInput` TS types and `listRegions()` (Task 8's DivisionForm imports these); `regions` PageMark; `/admin/regions[...]` routes; "Regions" nav item.

- [ ] **Step 1: API module** `frontend/src/api/regions.ts` (mirror `divisions.ts`):

```ts
import { api } from './client'

export interface Region {
  id: string
  name: string
  active: boolean
  vp_approver_ids: string[]
  vp_approver_names?: string[]
  division_count?: number
}

export interface RegionInput {
  name: string
  active?: boolean
  vp_approver_ids?: string[]
}

export function listRegions(): Promise<Region[]> {
  return api<Region[]>('/regions')
}
export function createRegion(body: RegionInput): Promise<Region> {
  return api<Region>('/regions', { method: 'POST', body })
}
export function updateRegion(id: string, body: RegionInput): Promise<Region> {
  return api<Region>(`/regions/${id}`, { method: 'PATCH', body })
}
```

- [ ] **Step 2: Nav icon.** In `NavIcons.tsx`, after `DivisionsIcon` (folded-map motif, same 24px line style):

```tsx
export function RegionsIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4z" />
      <path d="M9 4v14M15 6v14" />
    </Icon>
  )
}
```

- [ ] **Step 3: BrandCard mark.** Add `'regions'` to the `PageMark` union and `regions: RegionsIcon` to `MARKS` (import it). Add `'regions'` to the mark list in `BrandCard.test.tsx`.

- [ ] **Step 4: Pages.** Clone the Division admin quartet, renamed for regions; differences only where noted.

`RegionForm.tsx` (from `DivisionForm.tsx`: no number field; VP label):

```tsx
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
```

`RegionsPage.tsx` — clone `DivisionsPage.tsx`: `mark="regions"`, title "Regions", subtitle "Regions & their VP (Level-2) approver pools", "Add region" → `/admin/regions/new`; table columns Name / VPs (`r.vp_approver_names?.join(', ') || '—'`) / Divisions (`r.division_count ?? 0`) / Active / Edit → `/admin/regions/${r.id}`.

`RegionNewPage.tsx` / `RegionEditPage.tsx` — clone the Division new/edit pages 1:1, swapping `createDivision/updateDivision/listDivisions` for the region functions, query key `['regions']`, navigate target `/admin/regions`, and `RegionForm`.

- [ ] **Step 5: Routes and nav.** `App.tsx`: three routes inside `AdminLayout`, above the division routes:

```tsx
<Route path="/admin/regions" element={<RegionsPage />} />
<Route path="/admin/regions/new" element={<RegionNewPage />} />
<Route path="/admin/regions/:id" element={<RegionEditPage />} />
```

`AppShell.tsx`: import `RegionsIcon`; in the Admin section, insert above Divisions:

```tsx
{ to: '/admin/regions', label: 'Regions', icon: RegionsIcon, roles: ['ADMIN'] },
```

- [ ] **Step 6: Verify** — from `frontend/`: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` and `node ./node_modules/vitest/vitest.mjs run` → green; `node ./node_modules/vite/bin/vite.js build` → succeeds.

- [ ] **Step 7: Commit** — `feat(admin): Regions page — VP approver pools per region`

---

### Task 8: Division form requires a region; divisions list shows it

**Files:**
- Modify: `frontend/src/api/divisions.ts`, `frontend/src/routes/admin/DivisionForm.tsx`, `frontend/src/routes/admin/DivisionNewPage.tsx`, `frontend/src/routes/admin/DivisionEditPage.tsx`, `frontend/src/routes/admin/DivisionsPage.tsx`
- Test: create `frontend/src/routes/admin/DivisionForm.test.tsx`

**Interfaces:**
- Consumes: `listRegions()`/`Region` from Task 7; `region_id`/`region_name` from Task 2.

- [ ] **Step 1: Types.** In `divisions.ts` add to `Division`: `region_id: string | null` and `region_name?: string | null`; to `DivisionInput`: `region_id: string` (required — the form always supplies it).

- [ ] **Step 2: Failing form test**, `DivisionForm.test.tsx` (follow the setup style of an existing vitest file, e.g. `RequestSectionsPage.test.tsx`): render `DivisionForm` with two regions and no division; assert a "Region" combobox exists with a disabled "Select a region…" placeholder option and `required`; submitting with a region selected calls `onSubmit` with that `region_id`.

- [ ] **Step 3: Implement.** `DivisionForm` gains a `regions: Region[]` prop and state `const [regionId, setRegionId] = useState(division?.region_id ?? '')`. Insert between Name and the L1 TransferList (check `components/ui/Select`'s actual props before writing — mirror how another page uses it; if it doesn't fit a placeholder option, use a plain `<select>` styled like `Input`):

```tsx
      <div className="max-w-lg space-y-1">
        <label className="text-sm font-medium">Region</label>
        <Select value={regionId} onChange={(e) => setRegionId(e.target.value)} required>
          <option value="" disabled>Select a region…</option>
          {regions.filter((r) => r.active || r.id === division?.region_id).map((r) => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </Select>
      </div>
```

`onSubmit` body becomes `{ number, name, active, l1_approver_ids: l1Ids, region_id: regionId }`. In `DivisionNewPage`/`DivisionEditPage`, add `const { data: regions = [] } = useQuery({ queryKey: ['regions'], queryFn: listRegions })` and pass `regions` down. `DivisionsPage`: add a Region column (`d.region_name ?? '—'`) between Name and Active.

- [ ] **Step 4: Verify** — `node ./node_modules/vitest/vitest.mjs run` and tsc → green.

- [ ] **Step 5: Commit** — `feat(admin): division form requires a region; list shows it`

---

### Task 9: Thresholds page — L2 pool moves to regions

**Files:**
- Modify: `frontend/src/routes/admin/ThresholdsPage.tsx:53-66`

**Interfaces:** none new. Backend threshold PUT keeps accepting `approver_ids` for every level (the L2 ones are simply never read); no API change.

- [ ] **Step 1: Implement.** In the approvers block, branch level 2 like level 1 (label text `Approvers {r.level === 3 ? '(any one may approve)' : r.level === 2 ? '(set per region)' : '(set per division)'}`):

```tsx
                {r.level === 1 ? (
                  <p className="text-sm text-muted">Level-1 approvers are configured on each division.</p>
                ) : r.level === 2 ? (
                  <p className="text-sm text-muted">Level-2 approvers come from each region's VP list (Admin → Regions).</p>
                ) : (
                  <TransferList
                    options={approvers.map((u) => ({ id: u.id, label: `${u.name} (${u.email})` }))}
                    selected={r.approver_ids}
                    onChange={(ids) => setRow(r.level, { approver_ids: ids })}
                  />
                )}
```

- [ ] **Step 2: Verify** — tsc + `node ./node_modules/vite/bin/vite.js build` → green.

- [ ] **Step 3: Commit** — `feat(thresholds): L2 approver pool now lives on regions; page points there`

---

### Task 10: Docs, full verification, end-to-end check

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md.** Data model: add **Region** (name, active, `vp_approvers` via `region_vp_approvers`; L2 pool) and `Division.region_id` (nullable column, required by the form). Roles & approval workflow: L2 comes from the request's division's region; the requestor is excluded from every pool (including as a delegate); empty levels are skipped upward so every request gets at least one non-requestor approval (escalating past `required_levels` when needed; submit fails if nobody anywhere); submit may open at a level above 1. Backend layout: `regions` blueprint + `region_service`. Frontend layout: Regions admin pages; BrandCard mark `regions`. Note the L2 `ApprovalThreshold.approvers` column is vestigial.

- [ ] **Step 2: Full verification.** `cd backend && .venv/Scripts/python -m pytest -q` (expect the count to have grown from 271); from `frontend/`: tsc, vitest, `vite build` — all green. State the actual outputs.

- [ ] **Step 3: End-to-end.** Invoke the project's `verify` skill to build/launch the app and walk: Admin → Regions → create region with a VP; assign a division to it; submit a request above the L2 cap; approve at L1; confirm it lands PENDING_L2 with the region VP; also submit a request as a user who is that division's only L1 approver and confirm it opens at L2 directly.

- [ ] **Step 4: Commit** — `docs: CLAUDE.md for regions, region-VP L2 routing, and self-approval rules`
