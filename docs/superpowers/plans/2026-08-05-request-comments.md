# Request Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let anyone who can see a CAPEX request post an immutable comment on it, so an approver can ask a question instead of being forced to approve or reject.

**Architecture:** A new `RequestComment` table hanging off `capex_requests`, one `POST /api/requests/<id>/comments` route that returns the whole refreshed request, comments carried on the existing `request_out` payload (no new GET), a sixth editable email template that notifies the other side of the conversation, a `CommentThread` React component on the detail page, and a Comments section in the record PDF. Commenting changes no workflow state whatsoever.

**Tech Stack:** Flask 3 + SQLAlchemy 2.0 typed `Mapped` + Alembic, Pydantic v2, pytest; React 19 + TypeScript + TanStack Query + Tailwind v4, vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-05-request-comments-design.md`

## Global Constraints

- **Windows/`&`-in-path:** never run `npm run …`. Call binaries through node: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `node ./node_modules/vitest/vitest.mjs run`, `node ./node_modules/vite/bin/vite.js build`, all from `frontend/`.
- **Backend tests:** `cd backend && pytest -q` (236 tests pass before this work; the count only grows).
- Routes stay thin; logic lives in `services/`. Handled API errors raise `ServiceError(msg, status)`.
- **Notifications fire from blueprints, never from services.**
- Pydantic constraints must be expressed as **types** (`Annotated` + `StringConstraints`), never a `field_validator` that raises — a raising validator returns 500 instead of 400 because of the known `err.errors()` bug in `app/__init__.py`.
- Editable email template bodies must be Quill-round-trippable: `<p>`, `<strong>`, `<blockquote>`, `<br>` only. No tables, no `bgcolor`, no VML.
- Any test that patches `app.services.email_outlook.send` must accept `html=None, attachments=None` kwargs.
- Frontend styling uses the semantic tokens (`surface`, `surface-2`, `border`, `fg`, `muted`, `accent`), not hard-coded `slate-*`. Data-table `thead` rows use the sky brand tint.
- Comments are immutable: no `updated_at`, no edit/delete route, ever.
- Money/format helpers already exist — do not write new ones.

---

## File Structure

**Create**
| File | Responsibility |
| --- | --- |
| `backend/app/services/comment_service.py` | Add a comment; authz delegated to `request_service.get_request` |
| `backend/migrations/versions/a1b2c3d4e5f6_request_comments.py` | The `request_comments` table |
| `backend/tests/test_comments.py` | Model/service/API/notification tests for the feature |
| `frontend/src/components/CommentThread.tsx` | The thread UI + post box |
| `frontend/src/components/CommentThread.test.tsx` | Its vitest |
| `frontend/src/routes/formatDate.ts` | `formatActionDate`, shared by the detail page and the thread |

**Modify**
| File | Change |
| --- | --- |
| `backend/app/models/__init__.py` | `RequestComment` model + `CapexRequest.comments` |
| `backend/app/schemas/request.py` | `CommentIn` |
| `backend/app/services/request_service.py` | `comments` in `request_out`; `_can_view` pool fix |
| `backend/app/blueprints/requests.py` | `POST /<id>/comments` |
| `backend/app/services/email_frame.py` | `BUTTONS["COMMENT"]` |
| `backend/app/services/email_template_service.py` | `COMMENT` type, name, tokens, default, sample context |
| `backend/app/services/notify.py` | `notify_comment` |
| `backend/app/services/pdf_service.py` | Comments section |
| `backend/tests/test_pdf_service.py` | Comments-section cases |
| `frontend/src/api/requests.ts` | `RequestComment`, `comments`, `addComment` |
| `frontend/src/components/ActionIcons.tsx` | `CommentIcon` |
| `frontend/src/routes/RequestDetailPage.tsx` | Render `CommentThread`; import shared `formatActionDate` |
| `frontend/src/routes/RequestDetailPage.test.tsx` | `comments: []` in the mock, mock `addComment` |
| `CLAUDE.md`, `PHASE2-PROPOSALS.md` | Docs |

---

## Task 1: The `RequestComment` model and migration

**Files:**
- Modify: `backend/app/models/__init__.py` (after `ApprovalAction`, ~line 241)
- Create: `backend/migrations/versions/a1b2c3d4e5f6_request_comments.py`
- Test: `backend/tests/test_comments.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `RequestComment(id, request_id, author_id, body, created_at)` with relationships `.author -> User` and `.request -> CapexRequest`; `CapexRequest.comments -> list[RequestComment]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_comments.py`:

```python
from app.extensions import db
from app.models import RequestComment
from tests.factories import make_user, make_division, make_draft


def test_comment_belongs_to_a_request_and_an_author(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)

    db.session.add(RequestComment(request_id=req.id, author_id=owner.id, body="Why this model?"))
    db.session.commit()

    assert [c.body for c in req.comments] == ["Why this model?"]
    assert req.comments[0].author.name == owner.name
    assert req.comments[0].created_at is not None


def test_deleting_a_request_takes_its_comments_with_it(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)
    db.session.add(RequestComment(request_id=req.id, author_id=owner.id, body="x"))
    db.session.commit()

    db.session.delete(req)
    db.session.commit()

    assert db.session.query(RequestComment).count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_comments.py -q`
Expected: FAIL — `ImportError: cannot import name 'RequestComment' from 'app.models'`

- [ ] **Step 3: Add the model**

In `backend/app/models/__init__.py`, add after the `ApprovalAction` class:

```python
class RequestComment(db.Model):
    """A question or answer on a request. Immutable: no edit, no delete."""
    __tablename__ = "request_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="CASCADE")
    )
    request: Mapped["CapexRequest"] = relationship(back_populates="comments")
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"))
    author: Mapped["User"] = relationship("User")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
```

And inside `CapexRequest`, next to the other relationship declarations (after `actions`, ~line 188):

```python
    comments: Mapped[list["RequestComment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan",
        order_by="RequestComment.created_at",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_comments.py -q`
Expected: 2 passed. (The test fixture uses `db.create_all()`, so it passes before the migration exists — the migration is still required for the dev and prod databases.)

- [ ] **Step 5: Generate and clean up the migration**

Run: `cd backend && flask db revision --rev-id a1b2c3d4e5f6 -m "request comments"`

Then write its `upgrade`/`downgrade` bodies by hand (autogenerate is not used in this repo's history — match the existing hand-written files):

```python
def upgrade():
    op.create_table(
        "request_comments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.String(length=36), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["capex_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("request_comments")
```

Set `down_revision` to the current head. Find it with `cd backend && flask db heads`.

- [ ] **Step 6: Verify the migration runs**

Run: `cd backend && flask db upgrade && flask db current`
Expected: no error; `a1b2c3d4e5f6` reported as current.

- [ ] **Step 7: Run the whole backend suite**

Run: `cd backend && pytest -q`
Expected: all pass (238 now).

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/__init__.py backend/migrations/versions/a1b2c3d4e5f6_request_comments.py backend/tests/test_comments.py
git commit -m "feat(comments): add RequestComment model and migration"
```

---

## Task 2: `_can_view` lets pool approvers in

**Files:**
- Modify: `backend/app/services/request_service.py:22-27`
- Test: `backend/tests/test_request_service.py`

**Interfaces:**
- Consumes: `workflow_service.eligible_actors(level, division, thresholds)` and `threshold_service.list_thresholds()` (both already exist).
- Produces: `_can_view` / `can_view` now return `True` for any eligible approver at a pending request's current level. Every caller of `get_request` — detail page, PDF download, attachments, and Task 4's comment route — inherits this.

**Why:** `assignee_id` is only a display hint (the first of the level's approver pool). A second pool approver sees the request on their "assigned" worklist, clicks it, and gets a 403 today — even though `workflow_service.approve` would accept their decision. Pre-existing bug; fixing it is a precondition for comments being usable by the people this feature is for.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_request_service.py`:

```python
def test_pool_approver_who_is_not_the_assignee_can_view(app):
    from app.services import request_service
    from tests.factories import make_user, make_division, make_draft, set_thresholds

    first = make_user("first")
    second = make_user("second")
    owner = make_user("owner2", roles='["REQUESTOR"]')
    div = make_division(number="200", l1_approver_ids=[first.id, second.id])
    set_thresholds()
    req = make_draft(owner.id, div.id, number="CX000900")
    req.status, req.current_level, req.assignee_id = "PENDING_L1", 1, first.id
    db.session.commit()

    # `second` is in the L1 pool but is not the displayed assignee.
    assert request_service.can_view(req, second) is True


def test_unrelated_user_still_cannot_view(app):
    from app.services import request_service
    from tests.factories import make_user, make_division, make_draft, set_thresholds

    approver = make_user("appr3")
    stranger = make_user("stranger", roles='["REQUESTOR"]')
    owner = make_user("owner3", roles='["REQUESTOR"]')
    div = make_division(number="201", l1_approver_id=approver.id)
    set_thresholds()
    req = make_draft(owner.id, div.id, number="CX000901")
    req.status, req.current_level = "PENDING_L1", 1
    db.session.commit()

    assert request_service.can_view(req, stranger) is False
```

Check the file's existing imports; add `from app.extensions import db` and any factory imports at the top only if they are not already there.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_request_service.py -q -k pool_approver`
Expected: FAIL — `assert False is True`

- [ ] **Step 3: Widen `_can_view`**

Replace `_can_view` in `backend/app/services/request_service.py`:

```python
def _can_view(req, viewer):
    if viewer.id in (req.requestor_id, req.assignee_id):
        return True
    roles = viewer.roles_list
    if "ADMIN" in roles or "FINANCE" in roles:
        return True
    # assignee_id is only a display hint: a pending request belongs to the whole
    # eligible pool at its level, and any one of them may act on it.
    if req.status.startswith("PENDING_L"):
        from app.services import threshold_service, workflow_service
        actors = workflow_service.eligible_actors(
            req.current_level, req.division, threshold_service.list_thresholds())
        return viewer.id in {u.id for u in actors}
    return False
```

The import stays inside the function, matching how `list_requests` and `request_out` already dodge the `request_service` ↔ `workflow_service` circular import.

- [ ] **Step 4: Run the tests**

Run: `cd backend && pytest tests/test_request_service.py tests/test_requests_api.py tests/test_attachments_api.py tests/test_request_pdf_api.py tests/test_authz.py -q`
Expected: all pass, including both new tests.

- [ ] **Step 5: Run the whole backend suite**

Run: `cd backend && pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/request_service.py backend/tests/test_request_service.py
git commit -m "fix(requests): let every eligible pool approver view a pending request"
```

---

## Task 3: `CommentIn` schema and `comment_service`

**Files:**
- Modify: `backend/app/schemas/request.py`
- Create: `backend/app/services/comment_service.py`
- Test: `backend/tests/test_comments.py`

**Interfaces:**
- Consumes: `RequestComment` (Task 1), `request_service.get_request(request_id, viewer)` (widened in Task 2).
- Produces:
  - `CommentIn(body: str)` — strips whitespace, requires 1–4000 chars.
  - `comment_service.add_comment(request_id, viewer, body) -> RequestComment` — raises `ServiceError` (404/403) via `get_request`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_comments.py`:

```python
import pytest

from app.services import comment_service
from app.services.errors import ServiceError


def _owner_and_request():
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    return owner, make_draft(owner.id, div.id)


def test_add_comment_saves_and_returns_it(app):
    owner, req = _owner_and_request()

    c = comment_service.add_comment(req.id, owner, "Is this a replacement?")

    assert c.body == "Is this a replacement?"
    assert c.author_id == owner.id
    assert db.session.query(RequestComment).count() == 1


def test_add_comment_leaves_the_workflow_untouched(app):
    owner, req = _owner_and_request()
    req.status, req.current_level, req.required_levels = "PENDING_L2", 2, 3
    db.session.commit()

    comment_service.add_comment(req.id, owner, "Any update?")

    assert (req.status, req.current_level, req.assignee_id) == ("PENDING_L2", 2, None)


def test_add_comment_rejects_a_viewer_without_access(app):
    owner, req = _owner_and_request()
    stranger = make_user("stranger", roles='["REQUESTOR"]')

    with pytest.raises(ServiceError) as exc:
        comment_service.add_comment(req.id, stranger, "Nosy question")
    assert exc.value.status == 403


def test_add_comment_on_a_missing_request_is_404(app):
    owner, _ = _owner_and_request()

    with pytest.raises(ServiceError) as exc:
        comment_service.add_comment("no-such-id", owner, "Hello?")
    assert exc.value.status == 404
```

Add `RequestComment` to the existing `from app.models import ...` line at the top of the file if it is not already imported.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_comments.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.comment_service'`

- [ ] **Step 3: Write the service**

Create `backend/app/services/comment_service.py`:

```python
"""Comments on a request: a side conversation that changes no workflow state.

Authorization is deliberately delegated to `request_service.get_request`, so
"if you can see the request, you can comment on it" needs no second rule to
keep in sync.
"""
from app.extensions import db
from app.models import RequestComment
from app.services import request_service


def add_comment(request_id, viewer, body):
    req = request_service.get_request(request_id, viewer)
    comment = RequestComment(request_id=req.id, author_id=viewer.id, body=body)
    db.session.add(comment)
    db.session.commit()
    return comment
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_comments.py -q`
Expected: all pass.

- [ ] **Step 5: Write the failing schema test**

Append to `backend/tests/test_request_schemas.py`:

```python
def test_comment_in_strips_and_requires_a_body():
    from pydantic import ValidationError
    from app.schemas.request import CommentIn

    assert CommentIn(body="  Real question  ").body == "Real question"
    for bad in ("", "   ", "x" * 4001):
        with pytest.raises(ValidationError):
            CommentIn(body=bad)
```

Add `import pytest` at the top of that file if it is not already there.

- [ ] **Step 6: Run test to verify it fails**

Run: `cd backend && pytest tests/test_request_schemas.py -q -k comment_in`
Expected: FAIL — `ImportError: cannot import name 'CommentIn'`

- [ ] **Step 7: Add the schema**

In `backend/app/schemas/request.py`, add to the imports and then the class at the end of the file:

```python
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class CommentIn(BaseModel):
    # A type constraint, not a raising field_validator: a validator that raises
    # trips the app-wide ValidationError handler bug and returns 500, not 400.
    body: Annotated[str, StringConstraints(
        strip_whitespace=True, min_length=1, max_length=4000)]
```

Merge the `pydantic` import with the existing one rather than adding a second import line.

- [ ] **Step 8: Run the tests**

Run: `cd backend && pytest tests/test_request_schemas.py tests/test_comments.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/request.py backend/app/services/comment_service.py backend/tests/test_comments.py backend/tests/test_request_schemas.py
git commit -m "feat(comments): add CommentIn schema and comment_service"
```

---

## Task 4: Serialization and the POST route

**Files:**
- Modify: `backend/app/services/request_service.py` (`request_out`, after `"actions"`)
- Modify: `backend/app/blueprints/requests.py`
- Test: `backend/tests/test_comments.py`

**Interfaces:**
- Consumes: `comment_service.add_comment` (Task 3), `CommentIn` (Task 3).
- Produces:
  - `request_out(req)["comments"]` — a list of `{id, body, author_id, author_name, created_at}`, oldest first.
  - `POST /api/requests/<request_id>/comments` — body `{"body": "..."}`, returns `200` with the full request payload.

The route calls `notify.notify_comment` — written in Task 5. **This task stubs nothing:** write the route without the notify call now, and Task 5 adds the one line plus its test. That keeps each task independently green.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_comments.py`:

```python
def _login(client, user):
    client.post("/api/auth/login", json={"email": user.email, "password": "secret123"})


def test_post_comment_returns_the_request_with_the_comment(client, app):
    owner, req = _owner_and_request()
    _login(client, owner)

    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "Which vendor?"})

    assert r.status_code == 200
    body = r.get_json()
    assert body["id"] == req.id
    assert [c["body"] for c in body["comments"]] == ["Which vendor?"]
    assert body["comments"][0]["author_name"] == owner.name
    assert body["comments"][0]["created_at"] is not None


def test_comments_come_back_oldest_first(client, app):
    owner, req = _owner_and_request()
    _login(client, owner)

    client.post(f"/api/requests/{req.id}/comments", json={"body": "first"})
    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "second"})

    assert [c["body"] for c in r.get_json()["comments"]] == ["first", "second"]


def test_post_comment_rejects_an_empty_body_with_400(client, app):
    owner, req = _owner_and_request()
    _login(client, owner)

    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "   "})

    assert r.status_code == 400   # not 500 — see the ValidationError handler bug


def test_post_comment_rejects_an_overlong_body_with_400(client, app):
    owner, req = _owner_and_request()
    _login(client, owner)

    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "x" * 4001})

    assert r.status_code == 400


def test_post_comment_from_a_stranger_is_403(client, app):
    owner, req = _owner_and_request()
    stranger = make_user("stranger", roles='["REQUESTOR"]')
    _login(client, stranger)

    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "Nosy"})

    assert r.status_code == 403


def test_pool_approver_can_comment(client, app):
    from tests.factories import set_thresholds
    first = make_user("first")
    second = make_user("second")
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division(l1_approver_ids=[first.id, second.id])
    set_thresholds()
    req = make_draft(owner.id, div.id)
    req.status, req.current_level, req.assignee_id = "PENDING_L1", 1, first.id
    db.session.commit()
    _login(client, second)   # in the pool, not the displayed assignee

    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "Is the bid attached?"})

    assert r.status_code == 200
    assert r.get_json()["comments"][0]["author_name"] == second.name
```

Note the module already defines `_owner_and_request` (Task 3) — reuse it, don't redefine it.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_comments.py -q -k post_comment`
Expected: FAIL — 404 (route does not exist) / `KeyError: 'comments'`

- [ ] **Step 3: Serialize comments**

In `backend/app/services/request_service.py`, inside the `request_out` return dict, immediately after the `"actions"` entry:

```python
        "comments": [
            {"id": c.id, "body": c.body, "author_id": c.author_id,
             "author_name": c.author.name if c.author else None,
             "created_at": c.created_at.isoformat() if c.created_at else None}
            for c in sorted(req.comments, key=lambda x: (x.created_at, x.id))
        ],
```

- [ ] **Step 4: Add the route**

In `backend/app/blueprints/requests.py`, add `CommentIn` to the schema import and `comment_service` to the services import, then add the route after `resubmit_request`:

```python
@bp.post("/<request_id>/comments")
@login_required
def add_comment_route(request_id):
    data = CommentIn(**(request.get_json(silent=True) or {}))
    comment_service.add_comment(request_id, current_user, data.body)
    req = request_service.get_request(request_id, current_user)
    return jsonify(request_service.request_out(req))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_comments.py -q`
Expected: all pass.

- [ ] **Step 6: Run the whole backend suite**

Run: `cd backend && pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/request_service.py backend/app/blueprints/requests.py backend/tests/test_comments.py
git commit -m "feat(comments): POST /api/requests/<id>/comments and comments in request_out"
```

---

## Task 5: The `COMMENT` email template and `notify_comment`

**Files:**
- Modify: `backend/app/services/email_frame.py:35-45`
- Modify: `backend/app/services/email_template_service.py`
- Modify: `backend/app/services/notify.py`
- Modify: `backend/app/blueprints/requests.py` (one line in the route from Task 4)
- Test: `backend/tests/test_comments.py`

**Interfaces:**
- Consumes: `email_template_service.render/get/DEFAULTS`, `notify._send_template`, `workflow_service.eligible_actors`.
- Produces: `notify.notify_comment(req, comment)` where `comment` is a `RequestComment`. Emails go to the other side; `NotificationLog.type == "COMMENT"`.

**Recipients**

| Author | Recipients |
| --- | --- |
| The requestor | `PENDING_L*` → the eligible approver pool at `current_level`; `APPROVED` → every active FINANCE user; `DRAFT`/`REJECTED` → nobody |
| Anyone else | The requestor |

Never the author. Deduped by email.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_comments.py`:

```python
from app.models import NotificationLog
from app.services import notify
from tests.factories import set_thresholds


def _pending_l1():
    approver = make_user("appr")
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    set_thresholds()
    req = make_draft(owner.id, div.id)
    req.status, req.current_level, req.required_levels = "PENDING_L1", 1, 1
    db.session.commit()
    return approver, owner, req


def _recipients():
    return {r.recipient for r in db.session.query(NotificationLog)
            .filter_by(type="COMMENT").all()}


def test_requestor_comment_emails_the_current_approvers(app):
    approver, owner, req = _pending_l1()
    c = comment_service.add_comment(req.id, owner, "Any update?")

    notify.notify_comment(req, c)

    assert _recipients() == {approver.email}


def test_approver_comment_emails_the_requestor(app):
    approver, owner, req = _pending_l1()
    c = comment_service.add_comment(req.id, approver, "Is this a replacement?")

    notify.notify_comment(req, c)

    assert _recipients() == {owner.email}


def test_requestor_comment_on_an_approved_request_emails_finance(app):
    approver, owner, req = _pending_l1()
    finance = make_user("fin", roles='["FINANCE"]')
    req.status, req.assignee_id = "APPROVED", None
    db.session.commit()
    c = comment_service.add_comment(req.id, owner, "When is this booked?")

    notify.notify_comment(req, c)

    assert _recipients() == {finance.email}


def test_requestor_comment_on_a_draft_emails_nobody(app):
    owner, req = _owner_and_request()
    c = comment_service.add_comment(req.id, owner, "Note to self")

    notify.notify_comment(req, c)

    assert _recipients() == set()
    assert db.session.query(RequestComment).count() == 1   # the comment still saved


def test_comment_email_renders_the_author_and_body(app, monkeypatch):
    sent = {}
    monkeypatch.setattr("app.services.email_outlook.send",
                        lambda to, subject, body, html=None, attachments=None:
                        sent.update(subject=subject, html=html))
    app.config["EMAIL_ENABLED"] = True
    approver, owner, req = _pending_l1()
    c = comment_service.add_comment(req.id, approver, "Where are the bids?")

    notify.notify_comment(req, c)

    assert req.number in sent["subject"]
    assert approver.name in sent["html"]
    assert "Where are the bids?" in sent["html"]


def test_posting_a_comment_through_the_api_sends_the_email(client, app):
    approver, owner, req = _pending_l1()
    _login(client, owner)

    client.post(f"/api/requests/{req.id}/comments", json={"body": "Any update?"})

    assert _recipients() == {approver.email}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_comments.py -q -k "notify or emails"`
Expected: FAIL — `AttributeError: module 'app.services.notify' has no attribute 'notify_comment'`

- [ ] **Step 3: Register the button (no new artwork)**

In `backend/app/services/email_frame.py`, add to the `BUTTONS` dict:

```python
    # Reuses the approved button's PNG: its label already reads "View the request".
    "COMMENT": ("btn-approved", 162, 44, "View the request"),
```

- [ ] **Step 4: Add the template type**

In `backend/app/services/email_template_service.py`:

```python
TYPES = ("ASSIGNED", "APPROVED", "REJECTED", "FINANCE_READY", "FINANCE_COMPLETE",
         "COMMENT")
```

Add to `NAMES`: `"COMMENT": "New comment",`

Add to `TOKENS`:

```python
    "COMMENT": _COMMON + [
        {"token": "{author}", "description": "Name of the person who commented"},
        {"token": "{comment}", "description": "The comment text"},
    ],
```

Add to `DEFAULTS`:

```python
    "COMMENT": {
        "subject": "New comment on {number}",
        "body_html": (
            "<p><strong>{author}</strong> commented on request "
            "<strong>{number}</strong> ({total_cost}).</p><p><br></p>"
            "<blockquote>{comment}</blockquote><p><br></p>"
            "<p>Nothing has changed about where the request sits — it is still "
            "waiting on the same people.</p>" + _FACTS
        ),
    },
```

Add `"author": "Alex Kim",` to the dict in `sample_context` so the admin preview renders.

- [ ] **Step 5: Add `notify_comment`**

In `backend/app/services/notify.py`, after `notify_finance_complete`:

```python
def notify_comment(req, comment):
    """Tell the other side of the conversation. Never the author."""
    from app.services import threshold_service, workflow_service
    if comment.author_id == req.requestor_id:
        # Whoever is holding the request answers the requestor.
        if req.status.startswith("PENDING_L"):
            recipients = workflow_service.eligible_actors(
                req.current_level, req.division, threshold_service.list_thresholds())
        elif req.status == "APPROVED":
            recipients = [u for u in db.session.query(User)
                          .filter(User.active.is_(True)).all()
                          if "FINANCE" in u.roles_list]
        else:
            recipients = []          # DRAFT / REJECTED: nobody is waiting on it
        emails = [u.email for u in recipients]
    else:
        emails = [req.requestor.email] if req.requestor else []

    author = comment.author.name if comment.author else "Someone"
    author_email = comment.author.email if comment.author else None
    seen = set()
    for email in emails:
        if email == author_email or email in seen:
            continue
        seen.add(email)
        _send_template(email, "COMMENT", req, author=author, comment=comment.body)
```

- [ ] **Step 6: Wire the route**

In `backend/app/blueprints/requests.py`, change the comment route to capture the comment and notify:

```python
@bp.post("/<request_id>/comments")
@login_required
def add_comment_route(request_id):
    data = CommentIn(**(request.get_json(silent=True) or {}))
    comment = comment_service.add_comment(request_id, current_user, data.body)
    req = request_service.get_request(request_id, current_user)
    notify.notify_comment(req, comment)
    return jsonify(request_service.request_out(req))
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backend && pytest tests/test_comments.py -q`
Expected: all pass.

- [ ] **Step 8: Check the template-count assumptions elsewhere**

Run: `cd backend && pytest tests/test_email_templates.py tests/test_email_templates_api.py -q`
Expected: pass. If a test asserts a template count of 5 or iterates `TYPES` with a hard-coded list, update it to include `COMMENT` — that's a real behavior change, not a test to weaken.

- [ ] **Step 9: Run the whole backend suite**

Run: `cd backend && pytest -q`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/email_frame.py backend/app/services/email_template_service.py backend/app/services/notify.py backend/app/blueprints/requests.py backend/tests/
git commit -m "feat(comments): COMMENT email template notifying the other side"
```

---

## Task 6: Comments in the record PDF

**Files:**
- Modify: `backend/app/services/pdf_service.py` (`request_pdf_sections`, after the Approval history block)
- Test: `backend/tests/test_pdf_service.py`

**Interfaces:**
- Consumes: `req.comments` (Task 1), the existing `_datetime` and `_plain` helpers.
- Produces: a section `{"kind": "table", "title": "Comments", "rows": [...], "empty_note": ...}`. `render_pdf` needs no change — it already handles `kind: "table"`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_pdf_service.py`:

```python
def test_comments_section_lists_every_comment(app):
    from app.models import RequestComment
    from tests.factories import make_user as _mk
    req = _complete_request(app)
    asker = _mk("asker")
    db.session.add(RequestComment(request_id=req.id, author_id=asker.id,
                                  body="Where are the bids?"))
    db.session.commit()

    section = _by_title(pdf_service.request_pdf_sections(req, []), "Comments")

    assert section["rows"][0] == ["By", "Date", "Comment"]
    assert section["rows"][1][0] == asker.name
    assert section["rows"][1][2] == "Where are the bids?"
    assert section["empty_note"] is None


def test_comments_section_notes_when_there_are_none(app):
    req = _complete_request(app)

    section = _by_title(pdf_service.request_pdf_sections(req, []), "Comments")

    assert section["rows"] == []
    assert section["empty_note"] == "No comments."


def test_comments_section_follows_approval_history(app):
    req = _complete_request(app)
    titles = _titles(pdf_service.request_pdf_sections(req, []))

    assert titles.index("Comments") == titles.index("Approval history") + 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_pdf_service.py -q -k comments`
Expected: FAIL — `StopIteration` from `_by_title` (no such section)

- [ ] **Step 3: Add the section**

In `backend/app/services/pdf_service.py`, in `request_pdf_sections`, immediately after the Approval history `sections.append(...)` and before the Attachments one:

```python
    comments = sorted(req.comments, key=lambda c: (c.created_at is None, c.created_at))
    rows = []
    if comments:
        rows.append(["By", "Date", "Comment"])
        for c in comments:
            rows.append([c.author.name if c.author else "—",
                         _datetime(c.created_at), _plain(c.body)])
    sections.append({
        "kind": "table", "title": "Comments", "rows": rows,
        "empty_note": "No comments." if not comments else None,
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_pdf_service.py -q`
Expected: all pass.

- [ ] **Step 5: Verify a real PDF still renders**

Run: `cd backend && pytest tests/test_request_pdf_api.py -q`
Expected: pass (this exercises `render_pdf` end to end and would catch a malformed section dict).

- [ ] **Step 6: Run the whole backend suite**

Run: `cd backend && pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/pdf_service.py backend/tests/test_pdf_service.py
git commit -m "feat(comments): print the comment thread in the record PDF"
```

---

## Task 7: Frontend API types and the shared date helper

**Files:**
- Modify: `frontend/src/api/requests.ts`
- Create: `frontend/src/routes/formatDate.ts`
- Modify: `frontend/src/routes/RequestDetailPage.tsx` (delete the local `formatActionDate`, import it instead)
- Test: `frontend/src/api/requests.test.ts`

**Interfaces:**
- Produces:
  - `interface RequestComment { id: string; body: string; author_id: string; author_name: string | null; created_at: string | null }`
  - `CapexRequestData.comments: RequestComment[]`
  - `addComment(id: string, body: string): Promise<CapexRequestData>`
  - `formatActionDate(iso: string | null): string` exported from `routes/formatDate.ts`

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/api/requests.test.ts` (follow the file's existing mocking of `./client`):

```ts
it('posts a comment body to the comments endpoint', async () => {
  vi.mocked(api).mockResolvedValue({} as never)
  await addComment('req-1', 'Where are the bids?')
  expect(api).toHaveBeenCalledWith('/requests/req-1/comments', {
    method: 'POST', body: { body: 'Where are the bids?' },
  })
})
```

Add `addComment` to the file's import from `./requests`. If the existing tests mock `./client` differently, match that file's established pattern rather than introducing a new one.

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `node ./node_modules/vitest/vitest.mjs run src/api/requests.test.ts`
Expected: FAIL — `addComment is not a function` / TS error

- [ ] **Step 3: Add the type and the call**

In `frontend/src/api/requests.ts`, above `CapexRequestData`:

```ts
export interface RequestComment {
  id: string
  body: string
  author_id: string
  author_name: string | null
  created_at: string | null
}
```

Add to `CapexRequestData`, after `actions`:

```ts
  comments: RequestComment[]
```

And after `resubmitRequest`:

```ts
/** Post a comment. Changes no workflow state; returns the refreshed request. */
export function addComment(id: string, body: string): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}/comments`, { method: 'POST', body: { body } })
}
```

- [ ] **Step 4: Extract the date helper**

Create `frontend/src/routes/formatDate.ts` by moving the function verbatim out of `RequestDetailPage.tsx`:

```ts
export function formatActionDate(iso: string | null): string {
  if (!iso) return '—'
  // Backend timestamps are UTC; older rows may arrive without a zone marker.
  const d = new Date(/Z|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
  })
}
```

Delete the local copy from `RequestDetailPage.tsx` and add `import { formatActionDate } from './formatDate'` to its imports.

- [ ] **Step 5: Fix the detail page's test mock**

In `frontend/src/routes/RequestDetailPage.test.tsx`: add `comments: []` to the object returned by `makeRequest()`, and add `addComment: vi.fn(),` to the `vi.mock('../api/requests', ...)` factory.

- [ ] **Step 6: Typecheck and run the suite**

Run (from `frontend/`):
```
node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
node ./node_modules/vitest/vitest.mjs run
```
Expected: tsc clean; all vitest tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/requests.ts frontend/src/api/requests.test.ts frontend/src/routes/formatDate.ts frontend/src/routes/RequestDetailPage.tsx frontend/src/routes/RequestDetailPage.test.tsx
git commit -m "feat(comments): comment types and addComment client call"
```

---

## Task 8: The `CommentThread` component

**Files:**
- Create: `frontend/src/components/CommentThread.tsx`
- Create: `frontend/src/components/CommentThread.test.tsx`
- Modify: `frontend/src/components/ActionIcons.tsx`

**Interfaces:**
- Consumes: `CapexRequestData`, `RequestComment`, `addComment` (Task 7); `formatActionDate` from `routes/formatDate` (Task 7); `Button` from `components/ui/Button`; `ApiError` from `api/client`.
- Produces: `export function CommentThread({ req, onPosted }: { req: CapexRequestData; onPosted: (updated: CapexRequestData) => void })` and `export function CommentIcon(props: IconProps)`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/CommentThread.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { CommentThread } from './CommentThread'
import type { CapexRequestData } from '../api/requests'

vi.mock('../api/requests', () => ({ addComment: vi.fn() }))
import { addComment } from '../api/requests'

function makeReq(comments: CapexRequestData['comments'] = []): CapexRequestData {
  return { id: 'req-1', number: 'CX000042', comments } as CapexRequestData
}

describe('CommentThread', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows an empty state when there are no comments', () => {
    render(<CommentThread req={makeReq()} onPosted={() => {}} />)
    expect(screen.getByText('No comments yet.')).toBeInTheDocument()
  })

  it('lists existing comments with their author', () => {
    render(<CommentThread onPosted={() => {}} req={makeReq([
      { id: 'c1', body: 'Where are the bids?', author_id: 'u1',
        author_name: 'Approver', created_at: '2026-08-05T14:00:00' },
    ])} />)
    expect(screen.getByText('Where are the bids?')).toBeInTheDocument()
    expect(screen.getByText(/Approver/)).toBeInTheDocument()
  })

  it('disables the post button until something is typed', () => {
    render(<CommentThread req={makeReq()} onPosted={() => {}} />)
    const button = screen.getByRole('button', { name: /Post comment/i })
    expect(button).toBeDisabled()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Hi' } })
    expect(button).toBeEnabled()
  })

  it('posts the comment, clears the box, and hands back the updated request', async () => {
    const updated = makeReq([{ id: 'c1', body: 'Hi', author_id: 'u1',
      author_name: 'Me', created_at: null }])
    vi.mocked(addComment).mockResolvedValue(updated)
    const onPosted = vi.fn()
    render(<CommentThread req={makeReq()} onPosted={onPosted} />)

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Hi' } })
    fireEvent.click(screen.getByRole('button', { name: /Post comment/i }))

    await waitFor(() => expect(addComment).toHaveBeenCalledWith('req-1', 'Hi'))
    await waitFor(() => expect(onPosted).toHaveBeenCalledWith(updated))
    expect(screen.getByRole('textbox')).toHaveValue('')
  })

  it('shows an error and keeps the text when the post fails', async () => {
    vi.mocked(addComment).mockRejectedValue(new Error('boom'))
    render(<CommentThread req={makeReq()} onPosted={() => {}} />)

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Keep me' } })
    fireEvent.click(screen.getByRole('button', { name: /Post comment/i }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue('Keep me')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `node ./node_modules/vitest/vitest.mjs run src/components/CommentThread.test.tsx`
Expected: FAIL — cannot resolve `./CommentThread`

- [ ] **Step 3: Add the icon**

In `frontend/src/components/ActionIcons.tsx`, in the "approval actions" group:

```tsx
export function CommentIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M20 14a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z" />
      <path d="M8 9h8M8 12h5" />
    </Icon>
  )
}
```

- [ ] **Step 4: Write the component**

Create `frontend/src/components/CommentThread.tsx`:

```tsx
import { useState } from 'react'
import { addComment, type CapexRequestData } from '../api/requests'
import { ApiError } from '../api/client'
import { formatActionDate } from '../routes/formatDate'
import { Button } from './ui/Button'
import { CommentIcon } from './ActionIcons'

/**
 * The request's Q&A thread. Posting changes no workflow state — the request
 * stays with the same people at the same level — so an approver can ask a
 * question without having to reject.
 */
export function CommentThread({ req, onPosted }: {
  req: CapexRequestData
  onPosted: (updated: CapexRequestData) => void
}) {
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function post() {
    setErr(null)
    setBusy(true)
    try {
      const updated = await addComment(req.id, body.trim())
      setBody('')
      onPosted(updated)
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : 'Could not post the comment.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <h2 className="mb-1 flex items-center gap-1.5 font-semibold text-fg">
        <CommentIcon size={17} />Comments
      </h2>
      <ul className="space-y-2">
        {req.comments.map((c) => (
          <li key={c.id} className="rounded-md border border-border bg-surface-2 p-3 text-sm">
            <div className="mb-0.5 flex flex-wrap items-baseline gap-x-2">
              <span className="font-medium text-fg">{c.author_name ?? 'Unknown'}</span>
              <span className="text-xs text-muted">{formatActionDate(c.created_at)}</span>
            </div>
            <p className="whitespace-pre-wrap">{c.body}</p>
          </li>
        ))}
        {req.comments.length === 0 && <li className="text-sm text-muted">No comments yet.</li>}
      </ul>
      <div className="mt-2 space-y-2">
        <textarea
          className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent"
          rows={3}
          placeholder="Ask a question or answer one…"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        {err && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{err}</p>}
        <Button disabled={busy || !body.trim()} onClick={post}>
          <CommentIcon size={16} />Post comment
        </Button>
      </div>
    </section>
  )
}
```

- [ ] **Step 5: Run test to verify it passes**

Run (from `frontend/`): `node ./node_modules/vitest/vitest.mjs run src/components/CommentThread.test.tsx`
Expected: all 5 pass.

- [ ] **Step 6: Typecheck**

Run (from `frontend/`): `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/CommentThread.tsx frontend/src/components/CommentThread.test.tsx frontend/src/components/ActionIcons.tsx
git commit -m "feat(comments): CommentThread component and comment icon"
```

---

## Task 9: Render the thread on the request detail page

**Files:**
- Modify: `frontend/src/routes/RequestDetailPage.tsx`
- Test: `frontend/src/routes/RequestDetailPage.test.tsx`

**Interfaces:**
- Consumes: `CommentThread` (Task 8), the page's existing `qc.setQueryData(['request', id], …)` cache pattern.
- Produces: nothing downstream.

The thread renders at **every** status and deliberately ignores the hidden-wizard-sections config — like the Attachments section, it is not a wizard step.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/routes/RequestDetailPage.test.tsx`:

```tsx
describe('RequestDetailPage — comments', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRoles = ['APPROVER']
    vi.mocked(getHiddenSections).mockResolvedValue([])
  })

  it('shows the thread with existing comments', async () => {
    vi.mocked(getRequest).mockResolvedValue({
      ...makeRequest(),
      comments: [{ id: 'c1', body: 'Where are the bids?', author_id: 'approver-1',
        author_name: 'Approver', created_at: '2026-08-05T14:00:00' }],
    })
    renderPage()
    await screen.findByText('Request CX000042')
    expect(screen.getByText('Comments')).toBeInTheDocument()
    expect(screen.getByText('Where are the bids?')).toBeInTheDocument()
  })

  it('shows the thread on an approved request too', async () => {
    vi.mocked(getRequest).mockResolvedValue({ ...makeRequest(), status: 'APPROVED' })
    renderPage()
    await screen.findByText('Request CX000042')
    expect(screen.getByText('Comments')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `node ./node_modules/vitest/vitest.mjs run src/routes/RequestDetailPage.test.tsx`
Expected: FAIL — "Unable to find an element with the text: Comments"

- [ ] **Step 3: Render the thread**

In `frontend/src/routes/RequestDetailPage.tsx`, import it:

```tsx
import { CommentThread } from '../components/CommentThread'
```

and place it directly after the Approval history `</section>` (before the `req.status === 'APPROVED'` finance block):

```tsx
      <CommentThread req={req} onPosted={(updated) => qc.setQueryData(['request', id], updated)} />
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `node ./node_modules/vitest/vitest.mjs run src/routes/RequestDetailPage.test.tsx`
Expected: all pass.

- [ ] **Step 5: Full frontend gate**

Run (from `frontend/`):
```
node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
node ./node_modules/vitest/vitest.mjs run
node ./node_modules/vite/bin/vite.js build
```
Expected: clean typecheck, all tests pass, build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/RequestDetailPage.tsx frontend/src/routes/RequestDetailPage.test.tsx
git commit -m "feat(comments): show the comment thread on the request detail page"
```

---

## Task 10: End-to-end verification in the real app

**Files:** none changed unless a defect turns up.

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && pytest -q`
Expected: all pass.

- [ ] **Step 2: Run the full frontend gate**

Run (from `frontend/`):
```
node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
node ./node_modules/vitest/vitest.mjs run
node ./node_modules/vite/bin/vite.js build
```
Expected: all clean.

- [ ] **Step 3: Drive the app**

Use the project's `verify` skill (it builds the frontend, starts Flask on 5100, and drives a browser). Sign in as `admin@uniteduptime.com / ChangeMe123!` and confirm, on a request that is pending approval:

1. The **Comments** section appears under Approval history.
2. Posting a comment adds it to the thread without a page reload, and the box clears.
3. The request's **status, awaiting-approver list, and pipeline chips are unchanged** after posting — this is the whole point of the feature.
4. **Admin → Email Templates** now lists six templates, including **New comment**, and its preview renders with the `{author}` and `{comment}` tokens filled in.
5. **Download PDF** produces a document with a **Comments** section after Approval history.

- [ ] **Step 4: Record the evidence**

Note the actual pass counts and what was observed in the browser — these go in the final commit message. Do not claim a step passed without having run it.

---

## Task 11: Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `PHASE2-PROPOSALS.md`

- [ ] **Step 1: Update `CLAUDE.md`**

Four edits:

1. **Backend layout → `services/`**: add `comment_service` to the list — "comments on a request, authz delegated to `request_service.get_request`".
2. **Data model**: after the `ApprovalAction` entry, add **RequestComment** — `request_id`, `author_id`, `body`, `created_at`; immutable (no edit/delete route); cascades with the request.
3. **Roles & approval workflow**: note that an approver has a third response — a comment thread on the detail page that changes no workflow state, so questions no longer require a rejection. Note the recipient rule (requestor ↔ current holders) and that `_can_view` now admits every eligible pool approver, not just the displayed assignee.
4. **Email templates**: change "four editable email templates" / five-template references to **six**, and add `COMMENT` to the `EmailTemplate` type list. Note it reuses the `btn-approved` PNG.

Also update the **Record PDF** section: the document now includes a Comments section after the approval history.

- [ ] **Step 2: Update `PHASE2-PROPOSALS.md`**

Mark item 4 built, matching how items 2 and 5 are annotated:

```markdown
4. **Comment threads** — **BUILT 2026-08-05** (see
   `docs/superpowers/specs/2026-08-05-request-comments-design.md`).
   Q&A thread on the request detail page so approvers can ask questions
   without rejecting; immutable comments, email notification to the other
   party; request stays put in the workflow. Shipped with a sixth editable
   email template (`COMMENT`), the thread in the record PDF, and a fix for the
   `_can_view` bug that blocked non-assignee pool approvers.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md PHASE2-PROPOSALS.md
git commit -m "docs: record the request comments feature"
```

---

## Self-Review Notes

Spec coverage checked section by section: data model → Task 1; `_can_view` fix → Task 2; service + schema → Task 3; route + serialization → Task 4; email template + recipients → Task 5; PDF → Task 6; frontend types/API → Task 7; component + icon → Task 8; detail page → Task 9; test list → distributed across Tasks 1–9 and re-verified in Task 10; docs → Task 11.

Names are consistent across tasks: `RequestComment`, `comment_service.add_comment`, `CommentIn.body`, `request_out(...)["comments"]`, `notify.notify_comment(req, comment)`, `addComment(id, body)`, `CommentThread({ req, onPosted })`, `CommentIcon`, `formatActionDate`.
