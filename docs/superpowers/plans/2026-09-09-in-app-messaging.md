# CAPRI Pings (In-App Messaging) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any signed-in CAPRI user send other users a note, optionally about a capex request, see it in a header bell and a Messages page, reply in a thread, and tick it done.

**Architecture:** Two additive tables (`pings`, `ping_recipients`) behind a fat `ping_service` and a thin `pings` blueprint, following CAPRI's existing layering. A reply is a child row whose `parent_id` is the conversation root, so one exchange is one list item. Read state is per recipient; done state is shared across the roster and derived at read time, never stored. The frontend adds a header bell polling an unread count through TanStack Query, a slide-over quick view, a full-page Messages table with inline row expansion, and one shared New Ping modal behind every entry point. **This is a port of SCORE's shipped Pings** (`bid_template/bid_app`, same stack) with the bid/customer/approval-rule/line context replaced by one optional `request_id`.

**Tech Stack:** Flask blueprints, SQLAlchemy 2 typed models, Alembic, Pydantic v2, Flask-Login; React 19 + TypeScript + TanStack Query 5 + Tailwind v4 + Vite 6; pytest and vitest.

**Spec:** `docs/superpowers/specs/2026-09-09-in-app-messaging-design.md`

## Global Constraints

- **Repo:** everything in this plan lives in `capex_tracking/` (CAPRI). Paths below are relative to that root. The SCORE originals referenced for comparison live in `../bid_template/bid_app/`.
- **IDs are `String(36)`** with `default=_id` (`uuid.uuid4().hex`, from `app/models/__init__.py`) — never autoincrement, never SCORE's `String(32)` PK mixin.
- **Timestamps are plain `DateTime` with `default=_utcnow`**, like `RequestComment`. No `updated_at` on either table.
- **Naming is split on purpose:** the sidebar label, route and page are **Messages** / `/messages` / `MessagesPage.tsx`; everything else is **ping** — tables `pings` / `ping_recipients`, `ping_service.py`, `pings.py`, `schemas/pings.py`, `/api/pings`, `PingBell` / `PingPanel` / `PingCard` / `PingDetail` / `PingModal`, `api/pings.ts`. Never `message` in code, never `handoff`.
- **Every Ping button is `variant="primary" size="sm"`** (filled accent, small) with a 14px `SendIcon`; table-row Ping controls are icon-only `text-accent`.
- **Pings are unscoped**: `directory()` returns every active user; no `require_roles` on any ping route.
- **Ordering is `(last_activity_at DESC, last_activity_id DESC)`** — id is a tiebreaker, never a recency key.
- **Pydantic schemas use type constraints, never raising validators** (a raising `field_validator` turns a 400 into a 500 through `create_app`'s `ValidationError` handler). Blank-note and cap checks live in the service.
- **Frontend tooling is called through node** because the repo path contains `&`: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `node ./node_modules/vitest/vitest.mjs run`, `node ./node_modules/vite/bin/vite.js build`. Run from `frontend/`.
- **Frontend tests** start with `// @vitest-environment jsdom` and `import '@testing-library/jest-dom/vitest'` (vitest's default environment here is `node`).
- **Backend tests** run from `backend/` with `pytest -q`. Fixtures: `app`, `client` (conftest); factories `make_user(key, roles='["APPROVER"]')`, `make_division()`, `make_draft(requestor_id, division_id)`, `set_thresholds()` in `tests/factories.py`. `make_user` has no `active` parameter — set `u.active = False` and commit.
- **No email.** `ping_service` never imports `notify`.
- **Commits:** small, one per task, on `main` (CAPRI's history is direct commits). Prefix like the existing log: `feat(pings): …`, `test(pings): …`, `docs: …`.

## File Structure

**Backend (create):**
- `backend/app/services/ping_service.py` — all ping logic (create/list/get/reply/done/reopen/directory/suggestions, request summary, shared-done overlay).
- `backend/app/blueprints/pings.py` — thin routes under `/api/pings`.
- `backend/app/schemas/pings.py` — `PingCreateIn`, `PingReplyIn`.
- `backend/migrations/versions/e7f8a9b0c1d2_pings.py` — the two tables.
- `backend/tests/test_pings.py` — service + HTTP tests.

**Backend (modify):**
- `backend/app/models/__init__.py` — `Ping`, `PingRecipient` models appended after `RequestComment`.
- `backend/app/__init__.py` — register the blueprint.
- `backend/app/services/request_service.py` — `delete_draft` refuses a draft with pings (409).
- `backend/tests/test_delete_draft.py` — the 409 case.

**Frontend (create):**
- `frontend/src/api/pings.ts` — typed client + types.
- `frontend/src/components/PingBell.tsx`, `PingCard.tsx`, `PingDetail.tsx`, `PingModal.tsx`, `PingPanel.tsx` (+ `.test.tsx` for each except PingCard).
- `frontend/src/routes/MessagesPage.tsx` (+ `.test.tsx`).

**Frontend (modify):**
- `frontend/src/components/ui/Button.tsx` — `size` prop.
- `frontend/src/components/ActionIcons.tsx` — `SendIcon` (paper plane).
- `frontend/src/components/NavIcons.tsx` — `MessagesIcon`.
- `frontend/src/components/ui/BrandCard.tsx` — `messages` mark.
- `frontend/src/components/AppShell.tsx` — nav entry, bell + panel in the header.
- `frontend/src/App.tsx` — `/messages` route.
- `frontend/src/routes/RequestDetailPage.tsx` — Ping button.
- `frontend/src/routes/RequestsListPage.tsx` — row Ping icon on `RequestsTable` (shared with the Dashboard).
- `CLAUDE.md` — a "Pings" section.

---

### Task 1: Models and migration

**Files:**
- Modify: `backend/app/models/__init__.py` (append after `RequestComment`, before `NotificationLog`)
- Create: `backend/migrations/versions/e7f8a9b0c1d2_pings.py`
- Create: `backend/tests/test_pings.py`

**Interfaces:**
- Produces: `Ping(id, parent_id, sender_id, note, request_id, created_at)` and `PingRecipient(id, ping_id, user_id, read_at, completed_at)` importable from `app.models`. Unique constraint `uq_ping_recipient` on `(ping_id, user_id)`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_pings.py`:

```python
import pytest

from app.extensions import db
from tests.factories import make_user


def test_ping_tables_exist_and_relate(app):
    from app.models import Ping, PingRecipient

    sender = make_user("sam")
    recipient = make_user("rae")

    ping = Ping(sender_id=sender.id, note="Check the GL account.")
    db.session.add(ping)
    db.session.flush()
    db.session.add(PingRecipient(ping_id=ping.id, user_id=recipient.id))
    db.session.commit()

    assert len(ping.id) == 32          # uuid4().hex, in a String(36) column
    assert ping.parent_id is None
    assert ping.request_id is None
    assert ping.created_at is not None
    row = db.session.query(PingRecipient).one()
    assert row.read_at is None and row.completed_at is None


def test_ping_recipient_is_unique_per_person(app):
    from sqlalchemy.exc import IntegrityError

    from app.models import Ping, PingRecipient

    sender = make_user("sam")
    recipient = make_user("rae")
    ping = Ping(sender_id=sender.id, note="Hello")
    db.session.add(ping)
    db.session.flush()
    db.session.add(PingRecipient(ping_id=ping.id, user_id=recipient.id))
    db.session.add(PingRecipient(ping_id=ping.id, user_id=recipient.id))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
```

- [ ] **Step 2: Run to verify they fail**

Run from `backend/`: `pytest tests/test_pings.py -q`
Expected: FAIL with `ImportError: cannot import name 'Ping'`.

- [ ] **Step 3: Add the models**

In `backend/app/models/__init__.py`, after the `RequestComment` class and before `class NotificationLog`, add (`UniqueConstraint` must be added to the existing `from sqlalchemy import …` line at the top):

```python
class Ping(db.Model):
    """One note in a conversation. A REPLY IS A CHILD ROW, not a separate table:
    `parent_id` points at the conversation root and never at another reply, so a
    thread is exactly two levels deep and one exchange is one row in the inbox.

    Who it is addressed to lives in `ping_recipients` -- there is deliberately no
    recipient column here. Immutable once sent, so no updated_at.
    """
    __tablename__ = "pings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    parent_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("pings.id"), nullable=True, index=True)
    sender_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), index=True)
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    note: Mapped[str] = mapped_column(Text)
    # Optional context: the one thing a CAPRI ping can be "about". NO ACTION,
    # not cascade -- request_service.delete_draft refuses a draft with pings.
    request_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="NO ACTION"), nullable=True, index=True)
    request: Mapped[Optional["CapexRequest"]] = relationship("CapexRequest")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PingRecipient(db.Model):
    """Per-person state. Read is personal; done is SHARED and derived at read time
    (see ping_service.apply_shared_done) -- this row still records each person's
    own tick, so the roster can show who read and who closed it.
    """
    __tablename__ = "ping_recipients"
    __table_args__ = (
        # Addressing the same person twice is a dedupe bug, not a state the
        # database should hold.
        UniqueConstraint("ping_id", "user_id", name="uq_ping_recipient"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    ping_id: Mapped[str] = mapped_column(ForeignKey("pings.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), index=True)
    user: Mapped["User"] = relationship("User")
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pings.py -q`
Expected: 2 passed.

- [ ] **Step 5: Write the migration**

First confirm the head: from `backend/`, `flask db heads` should print `d4e5f6a7b8c9` (regions). If it prints something else, use that as `down_revision`.

Create `backend/migrations/versions/e7f8a9b0c1d2_pings.py`:

```python
"""pings + ping_recipients: in-app messaging

Purely additive -- no existing table is altered and nothing is backfilled.
A reply is a child row via pings.parent_id, never a separate table.

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("pings.id"), nullable=True),
        sa.Column("sender_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(36),
                  sa.ForeignKey("capex_requests.id", ondelete="NO ACTION"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_pings_parent_id", "pings", ["parent_id"])
    op.create_index("ix_pings_sender_id", "pings", ["sender_id"])
    op.create_index("ix_pings_request_id", "pings", ["request_id"])
    op.create_table(
        "ping_recipients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ping_id", sa.String(36),
                  sa.ForeignKey("pings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("ping_id", "user_id", name="uq_ping_recipient"),
    )
    op.create_index("ix_ping_recipients_user_id", "ping_recipients", ["user_id"])


def downgrade():
    op.drop_index("ix_ping_recipients_user_id", table_name="ping_recipients")
    op.drop_table("ping_recipients")
    op.drop_index("ix_pings_request_id", table_name="pings")
    op.drop_index("ix_pings_sender_id", table_name="pings")
    op.drop_index("ix_pings_parent_id", table_name="pings")
    op.drop_table("pings")
```

- [ ] **Step 6: Apply the migration to the dev database and check round-trip**

Run from `backend/` (venv active): `flask db upgrade`, then `flask db downgrade -1`, then `flask db upgrade`.
Expected: each command completes without error; `flask db current` ends on `e7f8a9b0c1d2 (head)`.

- [ ] **Step 7: Run the whole suite and commit**

Run: `pytest -q` — expected: all previous tests plus 2 new pass.

```bash
git add backend/app/models/__init__.py backend/migrations/versions/e7f8a9b0c1d2_pings.py backend/tests/test_pings.py
git commit -m "feat(pings): Ping and PingRecipient models with additive migration"
```

---

### Task 2: Create and list pings

**Files:**
- Create: `backend/app/services/ping_service.py`
- Test: `backend/tests/test_pings.py` (append)

**Interfaces:**
- Consumes: `Ping`, `PingRecipient`, `User` from Task 1; `ServiceError` from `app.services.errors`.
- Produces:
  - `create_ping(sender, *, recipient_ids: list[str], note: str, request_id: str | None = None, parent_id: str | None = None) -> Ping`
  - `list_pings(viewer, box: str) -> list[dict]` — each dict is the **summary shape**: `id, note, sender{id,name}, created_at, request_id, request{…}|None, recipients[{user_id,name,email,read_at,completed_at}], reply_count, unread_replies, unread_for_me, last_activity_id, last_activity_at, search_blob, completed_at, done_by`.
  - `apply_shared_done(payload, recipients) -> dict`, `_roster(ping_id) -> list[dict]`, `_summarize(ping, viewer) -> dict`, `_request_summary(viewer, request_id) -> dict | None` (used by Task 3).
  - `MAX_RECIPIENTS = 25`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_pings.py`:

```python
def test_create_ping_addresses_everyone_and_dedupes(app):
    from app.models import PingRecipient
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    b = make_user("ben")

    ping = ping_service.create_ping(
        sender, recipient_ids=[a.id, b.id, a.id], note="Please review.")

    rows = db.session.query(PingRecipient).filter_by(ping_id=ping.id).all()
    assert {r.user_id for r in rows} == {a.id, b.id}
    assert len(rows) == 2


def test_create_ping_refuses_a_blank_note(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    with pytest.raises(ServiceError) as excinfo:
        ping_service.create_ping(sender, recipient_ids=[a.id], note="   ")
    assert excinfo.value.status == 400


def test_create_ping_refuses_an_inactive_recipient(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    gone = make_user("gone")
    gone.active = False
    db.session.commit()
    with pytest.raises(ServiceError) as excinfo:
        ping_service.create_ping(sender, recipient_ids=[gone.id], note="Hi")
    assert excinfo.value.status == 400


def test_create_ping_refuses_too_many_recipients(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    ids = [make_user(f"m{i}").id for i in range(26)]
    with pytest.raises(ServiceError) as excinfo:
        ping_service.create_ping(sender, recipient_ids=ids, note="Hi")
    assert excinfo.value.status == 400


def test_create_ping_refuses_an_unknown_request(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    with pytest.raises(ServiceError) as excinfo:
        ping_service.create_ping(sender, recipient_ids=[a.id], note="Hi",
                                 request_id="no-such-request")
    assert excinfo.value.status == 400


def test_a_reply_cannot_attach_to_another_reply(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    root = ping_service.create_ping(sender, recipient_ids=[a.id], note="Root")
    reply = ping_service.create_ping(sender, recipient_ids=[a.id], note="Reply",
                                     parent_id=root.id)
    with pytest.raises(ServiceError) as excinfo:
        ping_service.create_ping(sender, recipient_ids=[a.id],
                                 note="Reply to reply", parent_id=reply.id)
    assert excinfo.value.status == 400


def test_inbox_lists_roots_for_the_recipient_and_sent_for_the_sender(app):
    from app.services import ping_service

    sender = make_user("sam")
    rae = make_user("rae")
    ping_service.create_ping(sender, recipient_ids=[rae.id], note="First")

    inbox = ping_service.list_pings(rae, "inbox")
    sent = ping_service.list_pings(sender, "sent")
    assert [p["note"] for p in inbox] == ["First"]
    assert [p["note"] for p in sent] == ["First"]
    assert ping_service.list_pings(sender, "inbox") == []
    assert inbox[0]["recipients"][0]["name"] == "Rae"
    assert inbox[0]["unread_for_me"] is True
    assert inbox[0]["request"] is None


def test_list_rejects_an_unknown_box(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    viewer = make_user("sam")
    with pytest.raises(ServiceError) as excinfo:
        ping_service.list_pings(viewer, "drafts")
    assert excinfo.value.status == 400


def test_ordering_is_deterministic_when_timestamps_tie(app):
    from datetime import datetime, timezone

    from app.models import Ping
    from app.services import ping_service

    sender = make_user("sam")
    rae = make_user("rae")
    first = ping_service.create_ping(sender, recipient_ids=[rae.id], note="First")
    second = ping_service.create_ping(sender, recipient_ids=[rae.id], note="Second")

    # Force a genuine tie so the only thing deciding the order is the id
    # tiebreak -- ids are uuid4().hex, NOT monotonic, hence "deterministic",
    # not "insertion order".
    tied_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.session.query(Ping).filter(Ping.id.in_([first.id, second.id])).update(
        {"created_at": tied_at}, synchronize_session=False)
    db.session.commit()

    inbox = ping_service.list_pings(rae, "inbox")
    assert [p["id"] for p in inbox] == sorted([first.id, second.id], reverse=True)


def test_summary_carries_the_live_request(app):
    from app.services import ping_service
    from tests.factories import make_division, make_draft

    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)
    rae = make_user("rae")

    ping_service.create_ping(owner, recipient_ids=[rae.id], note="See this",
                             request_id=req.id)

    summary = ping_service.list_pings(rae, "inbox")[0]["request"]
    assert summary["id"] == req.id
    assert summary["number"] == "CX000001"
    assert summary["status"] == "DRAFT"
    assert summary["requestor_name"] == "Owner"
    assert summary["total_cost"] is not None   # money_str of the stored total
    # Rae is neither the owner nor an approver: she can see the summary, not the request.
    assert summary["visible"] is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_pings.py -q`
Expected: the new tests FAIL with `ModuleNotFoundError: No module named 'app.services.ping_service'`.

- [ ] **Step 3: Write the service (create + list)**

Create `backend/app/services/ping_service.py`:

```python
"""Pings: in-app work routing with a conversation attached.

Two rules here are not obvious and are the whole point of the feature:

* **Read is personal.** Each recipient's own PingRecipient row carries read_at,
  so a group ping read by two of five is still unread for the other three.
* **Done is SHARED.** A group ping is one job, not one job each: whoever ticks
  it first closes it for the roster, and done_by names them. Derived here at
  read time rather than stored, so no schema or backfill is involved and each
  person's own tick survives if the rule is ever revisited.

Pings are deliberately UNSCOPED (spec section 5): anyone signed in can ping
anyone signed in, because the value is reaching whoever can answer fastest.
Do not add a scope filter to the directory.

Ported from SCORE's ping_service (bid_template/bid_app) with the bid, customer,
approval-rule and line context replaced by one optional request_id.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.extensions import db
from app.models import CapexRequest, Ping, PingRecipient, User
from app.serialization import money_str
from app.services import request_service
from app.services.errors import ServiceError

MAX_RECIPIENTS = 25


def _active_users(ids: list[str]) -> list[User]:
    rows = db.session.scalars(select(User).where(User.id.in_(ids))).all()
    found = {u.id: u for u in rows if u.active}
    missing = [i for i in ids if i not in found]
    if missing:
        raise ServiceError("Every recipient must be an active user.", 400)
    return [found[i] for i in ids]


def create_ping(sender, *, recipient_ids: list[str], note: str,
                request_id: str | None = None,
                parent_id: str | None = None) -> Ping:
    note = (note or "").strip()
    if not note:
        raise ServiceError("A ping needs a note.", 400)

    # dict.fromkeys dedupes while preserving the order the sender picked.
    ids = list(dict.fromkeys(recipient_ids or []))
    if not ids:
        raise ServiceError("A ping needs at least one recipient.", 400)
    if len(ids) > MAX_RECIPIENTS:
        raise ServiceError(
            f"A ping can go to at most {MAX_RECIPIENTS} people.", 400)
    _active_users(ids)

    if parent_id is not None:
        parent = db.session.get(Ping, parent_id)
        if parent is None or parent.parent_id is not None:
            # Replies attach to the ROOT, never to another reply: a thread is
            # exactly two levels deep.
            raise ServiceError("A reply must attach to a conversation.", 400)

    if request_id is not None and db.session.get(CapexRequest, request_id) is None:
        raise ServiceError("Unknown request.", 400)

    ping = Ping(parent_id=parent_id, sender_id=sender.id, note=note,
                request_id=request_id)
    db.session.add(ping)
    db.session.flush()
    for uid in ids:
        db.session.add(PingRecipient(ping_id=ping.id, user_id=uid))
    db.session.commit()
    return ping


def _iso(dt) -> str | None:
    """Datetimes leave the API isoformatted, like request_service does -- a raw
    datetime handed to jsonify serializes as an HTTP-date."""
    return dt.isoformat() if dt else None


def apply_shared_done(payload: dict, recipients: list[dict]) -> dict:
    """Overlay the SHARED completion onto a conversation.

    Earliest tick wins, so a second person ticking through a stale page cannot
    rewrite who finished it -- their tick is still on their own roster row.
    `recipients` carries raw datetimes (see `_roster`); sort on those, then
    isoformat only the value that leaves in the payload.
    """
    done = sorted((r["completed_at"], r["name"]) for r in recipients
                  if r.get("completed_at"))
    payload["completed_at"] = _iso(done[0][0]) if done else None
    payload["done_by"] = done[0][1] if done else None
    return payload


def _roster(ping_id: str) -> list[dict]:
    """Raw datetimes -- `apply_shared_done` sorts on them. `_serialize_recipient`
    isoformats them for the API payload."""
    rows = db.session.execute(
        select(PingRecipient, User)
        .join(User, User.id == PingRecipient.user_id)
        .where(PingRecipient.ping_id == ping_id)
        .order_by(User.name)).all()
    return [{"user_id": u.id, "name": u.name, "email": u.email,
             "read_at": r.read_at, "completed_at": r.completed_at}
            for r, u in rows]


def _serialize_recipient(r: dict) -> dict:
    return {**r, "read_at": _iso(r["read_at"]), "completed_at": _iso(r["completed_at"])}


def _request_summary(viewer, request_id: str | None) -> dict | None:
    """Identifying summary of the request a ping is about (spec section 4.1).

    It renders even when the viewer cannot open the request; only `visible`
    says whether the deep link should render too -- a link that 403s reads as
    broken software (spec section 5).
    """
    if request_id is None:
        return None
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        return None
    return {
        "id": req.id,
        "number": req.number,
        "status": req.status,
        "division_name": (f"{req.division.number} — {req.division.name}"
                          if req.division else None),
        "requestor_name": req.requestor.name if req.requestor else None,
        "total_cost": money_str(req.total_cost),
        "visible": request_service.can_view(req, viewer),
    }


def _summarize(ping: Ping, viewer) -> dict:
    # created_at first, id as a deterministic tiebreaker -- ids are uuid4().hex,
    # NOT monotonic, and cannot order by recency alone.
    replies = db.session.scalars(
        select(Ping).where(Ping.parent_id == ping.id)
        .order_by(Ping.created_at, Ping.id)).all()
    roster = _roster(ping.id)
    mine = next((r for r in roster if r["user_id"] == viewer.id), None)
    unread_replies = db.session.scalar(
        select(func.count(PingRecipient.id))
        .join(Ping, Ping.id == PingRecipient.ping_id)
        .where(Ping.parent_id == ping.id,
               PingRecipient.user_id == viewer.id,
               PingRecipient.read_at.is_(None))) or 0
    sender = db.session.get(User, ping.sender_id)
    # unread_for_me folds in unread REPLIES, not just the root row: a reply the
    # viewer has not opened must still bold the bell and the card, or the
    # summary disagrees with what unread_count (and the bell) already count.
    unread_for_me = bool(mine and mine["read_at"] is None) or unread_replies > 0
    last = replies[-1] if replies else ping
    payload = {
        "id": ping.id,
        "note": ping.note,
        "sender": {"id": sender.id, "name": sender.name},
        "created_at": _iso(ping.created_at),
        "request_id": ping.request_id,
        "request": _request_summary(viewer, ping.request_id),
        "recipients": [_serialize_recipient(r) for r in roster],
        "reply_count": len(replies),
        "unread_replies": unread_replies,
        "unread_for_me": unread_for_me,
        "last_activity_id": last.id,
        "last_activity_at": _iso(last.created_at),
        # Every reply's text, so the panel's search reaches a phrase said only
        # in a reply. The replies are already loaded above: no new query.
        "search_blob": " ".join(r.note for r in replies),
    }
    return apply_shared_done(payload, roster)


def list_pings(viewer, box: str) -> list[dict]:
    """Conversation roots only, newest activity first, capped at 200.

    A conversation the viewer STARTED returns to their inbox once someone
    replies: that reply is addressed to them, and the inbox is where they look
    for it. `sent` stays "exchanges I opened", so an answered ping is in both.
    """
    if box not in ("inbox", "sent"):
        raise ServiceError("box must be 'inbox' or 'sent'.", 400)

    if box == "sent":
        stmt = select(Ping).where(Ping.parent_id.is_(None),
                                  Ping.sender_id == viewer.id)
    else:
        addressed = (
            select(Ping.id)
            .join(PingRecipient, PingRecipient.ping_id == Ping.id)
            .where(PingRecipient.user_id == viewer.id))
        # A root is in my inbox if I am on the root OR on any of its replies.
        roots_via_replies = (
            select(Ping.parent_id).where(Ping.id.in_(addressed),
                                         Ping.parent_id.is_not(None)))
        stmt = select(Ping).where(
            Ping.parent_id.is_(None),
            Ping.id.in_(addressed.union(roots_via_replies)))

    roots = db.session.scalars(stmt).all()
    out = [_summarize(p, viewer) for p in roots]
    out.sort(key=lambda p: (p["last_activity_at"], p["last_activity_id"]),
             reverse=True)
    return out[:200]
```

Note `request_service.can_view` already exists (`request_service.py:39`) and wraps `_can_view`; `money_str` is in `app/serialization.py`. Check `app/services/__init__.py`: if it imports service modules by name, add `ping_service` there in the same style; if it is empty, nothing to do.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pings.py -q`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ping_service.py backend/tests/test_pings.py
git commit -m "feat(pings): create_ping and list_pings with request summary and shared-done overlay"
```

---

### Task 3: Detail, read stamping and thread membership

**Files:**
- Modify: `backend/app/services/ping_service.py` (append)
- Test: `backend/tests/test_pings.py` (append)

**Interfaces:**
- Consumes: `_summarize`, `_roster` from Task 2.
- Produces:
  - `get_ping(viewer, ping_id) -> dict` — the summary shape plus `replies: [{id, note, created_at, sender{id,name}}]`; 404 for unknown id or a reply's id; 403 unless the viewer is a thread participant; stamps this viewer's `read_at` on the root and every reply.
  - `unread_count(viewer) -> int`
  - `_may_see(viewer, ping) -> bool` (whole-thread membership; Task 4 reuses it).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_pings.py`:

```python
def test_detail_stamps_read_for_the_recipient_only(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    b = make_user("ben")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id, b.id], note="Hi")

    assert ping_service.unread_count(a) == 1
    assert ping_service.unread_count(b) == 1

    ping_service.get_ping(a, ping.id)

    # Read is PERSONAL: Ann's open must not clear Ben's badge.
    assert ping_service.unread_count(a) == 0
    assert ping_service.unread_count(b) == 1


def test_detail_refuses_a_third_party(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    nosy = make_user("nosy")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id], note="Hi")

    with pytest.raises(ServiceError) as excinfo:
        ping_service.get_ping(nosy, ping.id)
    assert excinfo.value.status == 403


def test_detail_404s_on_an_unknown_ping_and_on_a_replys_id(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    root = ping_service.create_ping(sender, recipient_ids=[a.id], note="Root")
    reply = ping_service.create_ping(sender, recipient_ids=[a.id], note="Reply",
                                     parent_id=root.id)
    for bad in ("no-such-id", reply.id):
        with pytest.raises(ServiceError) as excinfo:
            ping_service.get_ping(a, bad)
        assert excinfo.value.status == 404


def test_a_reply_only_recipient_may_open_the_conversation_their_inbox_lists(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    ben = make_user("ben")
    root = ping_service.create_ping(sender, recipient_ids=[a.id], note="Root")
    # Ben is addressed only on the REPLY, never on the root -- exactly the case
    # list_pings's roots_via_replies puts in his inbox, so get_ping must agree
    # or the inbox lists what the detail refuses.
    ping_service.create_ping(a, recipient_ids=[ben.id], note="Reply",
                             parent_id=root.id)

    assert [p["id"] for p in ping_service.list_pings(ben, "inbox")] == [root.id]
    assert ping_service.unread_count(ben) == 1
    detail = ping_service.get_ping(ben, root.id)
    assert [r["note"] for r in detail["replies"]] == ["Reply"]
    assert ping_service.unread_count(ben) == 0


def test_detail_has_iso_timestamps(app):
    import re

    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id], note="Hi")
    detail = ping_service.get_ping(a, ping.id)
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", detail["created_at"])
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", detail["recipients"][0]["read_at"])


def test_request_summary_is_visible_to_the_requestor(app):
    from app.services import ping_service
    from tests.factories import make_division, make_draft

    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)
    rae = make_user("rae")

    ping = ping_service.create_ping(rae, recipient_ids=[owner.id], note="Question",
                                    request_id=req.id)

    assert ping_service.get_ping(owner, ping.id)["request"]["visible"] is True
    assert ping_service.get_ping(rae, ping.id)["request"]["visible"] is False
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_pings.py -q`
Expected: the new tests FAIL with `AttributeError: module 'app.services.ping_service' has no attribute 'unread_count'` (or `get_ping`).

- [ ] **Step 3: Implement detail, read stamping, membership**

Append to `backend/app/services/ping_service.py`:

```python
def _may_see(viewer, ping: Ping) -> bool:
    """Membership is the WHOLE thread, not just the root.

    list_pings's roots_via_replies puts a root in someone's inbox when they are
    addressed only on a REPLY, never on the root itself -- so this must agree,
    or the inbox lists a conversation the detail view then refuses. Membership
    is: the root's sender, the root's recipients, every reply's sender, and
    every reply's recipients.
    """
    ping_ids = [ping.id] + list(db.session.scalars(
        select(Ping.id).where(Ping.parent_id == ping.id)).all())
    if db.session.scalar(
        select(func.count(Ping.id))
        .where(Ping.id.in_(ping_ids), Ping.sender_id == viewer.id)) > 0:
        return True
    return db.session.scalar(
        select(func.count(PingRecipient.id))
        .where(PingRecipient.ping_id.in_(ping_ids),
               PingRecipient.user_id == viewer.id)) > 0


def unread_count(viewer) -> int:
    return db.session.scalar(
        select(func.count(PingRecipient.id))
        .where(PingRecipient.user_id == viewer.id,
               PingRecipient.read_at.is_(None))) or 0


def _stamp_read(viewer, ping_ids: list[str]) -> None:
    """Stamp only THIS viewer's rows. Read is personal."""
    rows = db.session.scalars(
        select(PingRecipient).where(PingRecipient.ping_id.in_(ping_ids),
                                    PingRecipient.user_id == viewer.id,
                                    PingRecipient.read_at.is_(None))).all()
    if not rows:
        return
    now = datetime.now(timezone.utc)
    for row in rows:
        row.read_at = now
    db.session.commit()


def get_ping(viewer, ping_id: str) -> dict:
    ping = db.session.get(Ping, ping_id)
    if ping is None or ping.parent_id is not None:
        raise ServiceError("No such ping.", 404)
    if not _may_see(viewer, ping):
        raise ServiceError("Forbidden.", 403)

    replies = db.session.scalars(
        select(Ping).where(Ping.parent_id == ping.id)
        .order_by(Ping.created_at, Ping.id)).all()
    _stamp_read(viewer, [ping.id] + [r.id for r in replies])

    payload = _summarize(ping, viewer)
    payload["replies"] = [
        {"id": r.id, "note": r.note, "created_at": _iso(r.created_at),
         "sender": {"id": r.sender_id,
                    "name": db.session.get(User, r.sender_id).name}}
        for r in replies]
    return payload
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pings.py -q`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ping_service.py backend/tests/test_pings.py
git commit -m "feat(pings): get_ping with personal read stamping and whole-thread membership"
```

---

### Task 4: Reply, shared done, reopen, directory, suggestions

**Files:**
- Modify: `backend/app/services/ping_service.py` (append)
- Test: `backend/tests/test_pings.py` (append)

**Interfaces:**
- Consumes: `create_ping`, `_roster`, `_may_see`, `get_ping` from Tasks 2–3; `workflow_service.eligible_actors(level, division, thresholds, exclude_id=None)`; `threshold_service.list_thresholds()`.
- Produces:
  - `complete_ping(viewer, ping_id) -> dict`, `reopen_ping(viewer, ping_id) -> dict` — roster only (403 otherwise); return `get_ping`.
  - `reply(viewer, ping_id, note) -> Ping` — participant only; addresses everyone in the thread except the author.
  - `directory() -> list[dict]` — `{id, name, email, roles, division_name}` for every active user, by name.
  - `suggested_recipients(viewer, request_id) -> list[dict]` — same shape; 404 for an unknown request.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_pings.py`:

```python
def test_done_is_shared_and_earliest_tick_wins(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    b = make_user("ben")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id, b.id], note="Job")

    ping_service.complete_ping(a, ping.id)
    ping_service.complete_ping(b, ping.id)

    # One job, not one job each: Ann closed it for the roster and keeps the credit.
    for viewer in (a, b, sender):
        assert ping_service.get_ping(viewer, ping.id)["done_by"] == "Ann"
    roster = {r["name"]: r for r in ping_service.get_ping(a, ping.id)["recipients"]}
    # Ben's own tick is still recorded on his row.
    assert roster["Ben"]["completed_at"] is not None


def test_reopen_clears_this_persons_tick_and_falls_back_to_the_next_ticker(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    b = make_user("ben")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id, b.id], note="Job")
    ping_service.complete_ping(a, ping.id)
    ping_service.complete_ping(b, ping.id)
    ping_service.reopen_ping(a, ping.id)
    assert ping_service.get_ping(a, ping.id)["done_by"] == "Ben"
    ping_service.reopen_ping(b, ping.id)
    assert ping_service.get_ping(a, ping.id)["done_by"] is None


def test_done_and_reopen_refuse_a_non_recipient(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id], note="Job")
    # The sender is not on the roster, so the tick is not theirs to make.
    for fn in (ping_service.complete_ping, ping_service.reopen_ping):
        with pytest.raises(ServiceError) as excinfo:
            fn(sender, ping.id)
        assert excinfo.value.status == 403


def test_a_reply_returns_the_conversation_to_the_senders_inbox(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id], note="Question")

    assert ping_service.list_pings(sender, "inbox") == []
    ping_service.reply(a, ping.id, "Answer")

    inbox = ping_service.list_pings(sender, "inbox")
    assert [p["id"] for p in inbox] == [ping.id]
    assert inbox[0]["reply_count"] == 1
    assert inbox[0]["unread_for_me"] is True      # the unread REPLY counts
    assert "Answer" in inbox[0]["search_blob"]

    ping_service.get_ping(sender, ping.id)
    assert ping_service.list_pings(sender, "inbox")[0]["unread_for_me"] is False


def test_a_later_reply_reaches_everyone_the_conversation_has_ever_addressed(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    ben = make_user("ben")
    root = ping_service.create_ping(sender, recipient_ids=[a.id], note="Root")
    # A reply that added Ben -- a recipient the root never named.
    ping_service.create_ping(a, recipient_ids=[sender.id, ben.id],
                             note="Bringing Ben in", parent_id=root.id)

    further = ping_service.reply(sender, root.id, "Following up")
    assert ben.id in {r["user_id"] for r in ping_service._roster(further.id)}


def test_a_deactivated_participant_does_not_block_replies_to_the_rest(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    ben = make_user("ben")
    root = ping_service.create_ping(sender, recipient_ids=[a.id, ben.id], note="Root")
    ben.active = False
    db.session.commit()

    further = ping_service.reply(sender, root.id, "Following up")
    recipients = {r["user_id"] for r in ping_service._roster(further.id)}
    assert a.id in recipients and ben.id not in recipients


def test_reply_refuses_a_non_participant(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    nosy = make_user("nosy")
    root = ping_service.create_ping(sender, recipient_ids=[a.id], note="Root")
    with pytest.raises(ServiceError) as excinfo:
        ping_service.reply(nosy, root.id, "Butting in")
    assert excinfo.value.status == 403


def test_directory_is_unscoped_but_excludes_inactive(app):
    from app.services import ping_service
    from tests.factories import make_division

    div = make_division()
    dee = make_user("dee", roles='["ADMIN"]')
    dee.division_id = div.id
    make_user("eli", roles='["REQUESTOR"]')
    gone = make_user("gone")
    gone.active = False
    db.session.commit()

    users = {u["name"]: u for u in ping_service.directory()}
    assert "Dee" in users and "Eli" in users and "Gone" not in users
    assert users["Dee"]["roles"] == ["ADMIN"]
    assert users["Dee"]["division_name"] == "100 — Field Services"
    assert users["Eli"]["division_name"] is None


def test_suggestions_are_the_requestor_and_the_pending_pool_minus_the_viewer(app):
    from app.services import ping_service, workflow_service
    from tests.factories import make_division, make_draft, set_thresholds

    owner = make_user("owner", roles='["REQUESTOR"]')
    l1 = make_user("lone")
    l3 = make_user("lthree")
    div = make_division(l1_approver_id=l1.id)
    set_thresholds(l3_approver=l3.id)
    req = make_draft(owner.id, div.id)            # 30000 < L1 cap, so PENDING_L1
    workflow_service.submit(req.id, owner.id)
    assert req.status == "PENDING_L1"

    viewer = make_user("viewer")
    ids = [u["id"] for u in ping_service.suggested_recipients(viewer, req.id)]
    assert set(ids) == {owner.id, l1.id}

    # The viewer never suggests themself.
    ids = [u["id"] for u in ping_service.suggested_recipients(l1, req.id)]
    assert ids == [owner.id]


def test_suggestions_switch_to_finance_once_approved(app):
    from app.services import ping_service
    from tests.factories import make_division, make_draft

    owner = make_user("owner", roles='["REQUESTOR"]')
    fin = make_user("fin", roles='["FINANCE"]')
    make_user("approver")
    div = make_division()
    req = make_draft(owner.id, div.id)
    req.status = "APPROVED"
    db.session.commit()

    viewer = make_user("viewer")
    ids = {u["id"] for u in ping_service.suggested_recipients(viewer, req.id)}
    assert ids == {owner.id, fin.id}


def test_suggestions_404_an_unknown_request(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    viewer = make_user("viewer")
    with pytest.raises(ServiceError) as excinfo:
        ping_service.suggested_recipients(viewer, "no-such-request")
    assert excinfo.value.status == 404
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_pings.py -q`
Expected: the new tests FAIL with `AttributeError` on `complete_ping` / `reply` / `directory` / `suggested_recipients`.

- [ ] **Step 3: Implement**

Append to `backend/app/services/ping_service.py`:

```python
def _my_row(viewer, ping_id: str) -> PingRecipient:
    row = db.session.scalar(
        select(PingRecipient).where(PingRecipient.ping_id == ping_id,
                                    PingRecipient.user_id == viewer.id))
    if row is None:
        raise ServiceError("Forbidden.", 403)
    return row


def complete_ping(viewer, ping_id: str) -> dict:
    """Stamp only the ticker's row. The SHARED close is derived by
    apply_shared_done, so a later tick cannot rewrite who finished it."""
    row = _my_row(viewer, ping_id)
    if row.completed_at is None:
        row.completed_at = datetime.now(timezone.utc)
        db.session.commit()
    return get_ping(viewer, ping_id)


def reopen_ping(viewer, ping_id: str) -> dict:
    row = _my_row(viewer, ping_id)
    row.completed_at = None
    db.session.commit()
    return get_ping(viewer, ping_id)


def reply(viewer, ping_id: str, note: str) -> Ping:
    """A reply is addressed to the whole CONVERSATION, not just the root's
    roster -- root sender, root recipients, and every reply's own sender and
    recipients, minus this reply's author. This must agree with _may_see's
    whole-thread membership, or someone in the conversation stops receiving
    its replies. Inactive participants are filtered out here (not refused), so
    someone who has left cannot block replies for everyone else.
    """
    root = db.session.get(Ping, ping_id)
    if root is None or root.parent_id is not None:
        raise ServiceError("No such ping.", 404)
    if not _may_see(viewer, root):
        raise ServiceError("Forbidden.", 403)

    replies = db.session.scalars(
        select(Ping).where(Ping.parent_id == root.id)).all()
    party = {root.sender_id} | {r["user_id"] for r in _roster(root.id)}
    for r in replies:
        party.add(r.sender_id)
        party |= {rr["user_id"] for rr in _roster(r.id)}
    party.discard(viewer.id)
    if party:
        active = set(db.session.scalars(
            select(User.id).where(User.id.in_(party), User.active.is_(True))).all())
        party &= active
    if not party:
        raise ServiceError("There is nobody to reply to.", 400)
    return create_ping(viewer, recipient_ids=sorted(party), note=note,
                       parent_id=root.id)


def _user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "roles": u.roles_list,
            "division_name": (f"{u.division.number} — {u.division.name}"
                              if u.division else None)}


def directory() -> list[dict]:
    """Every active user. Deliberately UNSCOPED -- see the module docstring."""
    rows = db.session.scalars(
        select(User).where(User.active.is_(True)).order_by(User.name)).all()
    return [_user_out(u) for u in rows]


def suggested_recipients(viewer, request_id: str) -> list[dict]:
    """The people most likely to answer a request-attached ping, ranked first in
    the picker: the requestor; while pending, the eligible approver pool at the
    current level (the same `workflow_service.eligible_actors` the worklists
    use, with the requestor excluded exactly as everywhere else); once
    APPROVED, every active FINANCE user. The viewer is never suggested to
    themself. Matching is on user ids from the request's own fields, never on
    name text.
    """
    from app.services import threshold_service, workflow_service

    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)

    found: dict[str, User] = {}
    if req.requestor is not None and req.requestor.active:
        found[req.requestor.id] = req.requestor
    if req.status.startswith("PENDING_L"):
        for actor in workflow_service.eligible_actors(
                req.current_level, req.division, threshold_service.list_thresholds(),
                exclude_id=req.requestor_id):
            if actor.active:
                found.setdefault(actor.id, actor)
    elif req.status == "APPROVED":
        for u in db.session.scalars(
                select(User).where(User.active.is_(True))).all():
            if "FINANCE" in u.roles_list:
                found.setdefault(u.id, u)
    found.pop(viewer.id, None)
    return [_user_out(u) for u in sorted(found.values(), key=lambda u: u.name)]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pings.py -q`
Expected: 29 passed. If `test_suggestions_are_the_requestor_and_the_pending_pool_minus_the_viewer` fails on `req.status`, re-read the request with `db.session.get(CapexRequest, req.id)` after `submit` — `submit` works on its own loaded instance in the same session so the attribute should refresh, but the identity map is the thing to check.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ping_service.py backend/tests/test_pings.py
git commit -m "feat(pings): reply, shared done/reopen, unscoped directory, suggested recipients"
```

---

### Task 5: Schemas, blueprint, registration, draft-delete guard

**Files:**
- Create: `backend/app/schemas/pings.py`
- Create: `backend/app/blueprints/pings.py`
- Modify: `backend/app/__init__.py` (register after `request_sections_bp`)
- Modify: `backend/app/services/request_service.py:118-131` (`delete_draft`)
- Test: `backend/tests/test_pings.py` (append), `backend/tests/test_delete_draft.py` (append)

**Interfaces:**
- Produces the HTTP surface the frontend (Task 6) consumes:

| route | response |
|---|---|
| `GET /api/pings/unread_count` | `{"count": n}` |
| `GET /api/pings?box=inbox\|sent` | `{"pings": [summary…]}` |
| `GET /api/pings/directory` | `{"users": [user…]}` |
| `GET /api/pings/suggestions?request_id=` | `{"users": [user…]}`; 400 without `request_id` |
| `GET /api/pings/<id>` | `{"ping": detail}` |
| `POST /api/pings` | body `{recipient_ids, note, request_id?}` → `{"ping": detail}` |
| `POST /api/pings/<id>/reply` | body `{note}` → `{"ping": detail}` |
| `POST /api/pings/<id>/done` / `/reopen` | `{"ping": detail}` |

CAPRI's other blueprints return bare objects (no `ok` envelope) and errors as `{"error": msg}` via `create_app`'s handlers — follow that, not SCORE's `ok: true`.

- [ ] **Step 1: Write the failing HTTP tests**

Append to `backend/tests/test_pings.py`:

```python
def _login(client, key, roles='["APPROVER"]'):
    u = make_user(key, roles=roles)
    client.post("/api/auth/login", json={"email": f"{key}@x.com", "password": "secret123"})
    return u


def test_every_ping_route_requires_a_session(client):
    assert client.get("/api/pings/unread_count").status_code == 401
    assert client.get("/api/pings").status_code == 401
    assert client.post("/api/pings", json={}).status_code == 401


def test_post_get_and_list_pings_over_http(client, app):
    me = _login(client, "me")
    mate = make_user("mate")

    res = client.post("/api/pings", json={"recipient_ids": [mate.id],
                                          "note": "Please look at this."})
    assert res.status_code == 200
    ping_id = res.get_json()["ping"]["id"]

    body = client.get("/api/pings?box=sent").get_json()
    assert [p["note"] for p in body["pings"]] == ["Please look at this."]
    assert client.get("/api/pings").get_json()["pings"] == []       # my inbox
    detail = client.get(f"/api/pings/{ping_id}").get_json()["ping"]
    assert detail["sender"]["id"] == me.id and detail["replies"] == []


def test_blank_note_and_unknown_field_are_400s(client, app):
    _login(client, "me")
    mate = make_user("mate")
    assert client.post("/api/pings", json={"recipient_ids": [mate.id], "note": ""}
                       ).status_code == 400
    assert client.post("/api/pings", json={"recipient_ids": [mate.id], "note": "x",
                                           "bid_id": "b1"}).status_code == 400


def test_unread_count_reply_done_and_reopen_over_http(client, app):
    from app.services import ping_service

    me = _login(client, "me")
    other = make_user("other")
    ping = ping_service.create_ping(other, recipient_ids=[me.id], note="Yours")

    assert client.get("/api/pings/unread_count").get_json()["count"] == 1
    res = client.post(f"/api/pings/{ping.id}/reply", json={"note": "On it."})
    assert res.status_code == 200 and res.get_json()["ping"]["reply_count"] == 1
    assert client.post(f"/api/pings/{ping.id}/done").get_json()["ping"]["done_by"] == "Me"
    assert client.post(f"/api/pings/{ping.id}/reopen").get_json()["ping"]["done_by"] is None
    assert client.get("/api/pings/unread_count").get_json()["count"] == 0


def test_third_party_detail_is_403_over_http(client, app):
    from app.services import ping_service

    _login(client, "nosy")
    sender = make_user("sam")
    ann = make_user("ann")
    ping = ping_service.create_ping(sender, recipient_ids=[ann.id], note="Private")
    assert client.get(f"/api/pings/{ping.id}").status_code == 403


def test_directory_and_suggestions_over_http(client, app):
    from tests.factories import make_division, make_draft

    _login(client, "me")
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)

    names = [u["name"] for u in client.get("/api/pings/directory").get_json()["users"]]
    assert "Owner" in names and "Me" in names
    assert client.get("/api/pings/suggestions").status_code == 400
    suggested = client.get(f"/api/pings/suggestions?request_id={req.id}").get_json()["users"]
    assert [u["id"] for u in suggested] == [owner.id]
```

Append to `backend/tests/test_delete_draft.py`:

```python
def test_a_draft_with_pings_cannot_be_deleted(client, app):
    from app.services import ping_service

    owner = make_user("own", roles='["REQUESTOR"]')
    mate = make_user("mate")
    div = make_division()
    req = make_draft(owner.id, div.id)
    ping_service.create_ping(owner, recipient_ids=[mate.id], note="About this draft",
                             request_id=req.id)

    _login(client, "own")
    resp = client.delete(f"/api/requests/{req.id}")

    assert resp.status_code == 409
    assert "messages attached" in resp.get_json()["error"]
    assert db.session.get(CapexRequest, req.id) is not None
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/test_pings.py tests/test_delete_draft.py -q`
Expected: the HTTP tests FAIL with 404s (no routes); the delete test FAILS with `204 != 409`.

- [ ] **Step 3: Schema**

Create `backend/app/schemas/pings.py`:

```python
"""Input shapes for /api/pings.

Constraints are TYPES, not raising validators: a field_validator that raises
puts an unserializable object under errors()['ctx'] and the 400 becomes a 500
through create_app's ValidationError handler (same trap CommentIn avoids). The
blank-note and cap checks therefore live in ping_service as ServiceErrors.
"""
from pydantic import BaseModel, ConfigDict, Field


class PingCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_ids: list[str] = Field(min_length=1)
    note: str
    request_id: str | None = None


class PingReplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str
```

- [ ] **Step 4: Blueprint**

Create `backend/app/blueprints/pings.py`:

```python
"""Pings. Thin routes; everything lives in ping_service.

No require_roles: every role pings, and the directory is unscoped by design
(spec section 5). login_required alone is the gate. Static paths (unread_count,
directory, suggestions) are declared before /<ping_id> so Flask never treats
them as ids.
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.schemas.pings import PingCreateIn, PingReplyIn
from app.services import ping_service
from app.services.errors import ServiceError

bp = Blueprint("pings", __name__, url_prefix="/api/pings")


@bp.get("/unread_count")
@login_required
def unread_count():
    return jsonify(count=ping_service.unread_count(current_user))


@bp.get("")
@login_required
def list_pings():
    box = request.args.get("box") or "inbox"
    return jsonify(pings=ping_service.list_pings(current_user, box))


@bp.get("/directory")
@login_required
def directory():
    return jsonify(users=ping_service.directory())


@bp.get("/suggestions")
@login_required
def suggestions():
    request_id = request.args.get("request_id")
    if not request_id:
        raise ServiceError("request_id is required.", 400)
    return jsonify(users=ping_service.suggested_recipients(current_user, request_id))


@bp.get("/<ping_id>")
@login_required
def get_ping(ping_id):
    return jsonify(ping=ping_service.get_ping(current_user, ping_id))


@bp.post("")
@login_required
def create_ping():
    data = PingCreateIn(**(request.get_json(silent=True) or {}))
    ping = ping_service.create_ping(
        current_user, recipient_ids=data.recipient_ids, note=data.note,
        request_id=data.request_id)
    return jsonify(ping=ping_service.get_ping(current_user, ping.id))


@bp.post("/<ping_id>/reply")
@login_required
def reply(ping_id):
    data = PingReplyIn(**(request.get_json(silent=True) or {}))
    ping_service.reply(current_user, ping_id, data.note)
    return jsonify(ping=ping_service.get_ping(current_user, ping_id))


@bp.post("/<ping_id>/done")
@login_required
def done(ping_id):
    return jsonify(ping=ping_service.complete_ping(current_user, ping_id))


@bp.post("/<ping_id>/reopen")
@login_required
def reopen(ping_id):
    return jsonify(ping=ping_service.reopen_ping(current_user, ping_id))
```

In `backend/app/__init__.py`, directly after the `request_sections_bp` registration, add:

```python
    from .blueprints.pings import bp as pings_bp
    app.register_blueprint(pings_bp)
```

- [ ] **Step 5: Draft-delete guard**

In `backend/app/services/request_service.py`, inside `delete_draft`, after the `if req.status != "DRAFT":` check and before the storage import, add:

```python
    from app.models import Ping
    if db.session.query(Ping).filter(Ping.request_id == req.id).count():
        # Explicit, not left to the FK: CAPRI never turns on SQLite's
        # PRAGMA foreign_keys, so the NO ACTION FK alone would not fire in
        # dev or tests (spec section 2.1).
        raise ServiceError("This draft has messages attached and cannot be deleted.", 409)
```

- [ ] **Step 6: Run the suite**

Run: `pytest -q`
Expected: everything passes (271 previous + 36 new).

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/pings.py backend/app/blueprints/pings.py backend/app/__init__.py backend/app/services/request_service.py backend/tests/test_pings.py backend/tests/test_delete_draft.py
git commit -m "feat(pings): /api/pings blueprint and schemas; drafts with pings refuse deletion"
```

---

### Task 6: Frontend API client, Button size, icons, BrandCard mark

**Files:**
- Create: `frontend/src/api/pings.ts`
- Modify: `frontend/src/components/ui/Button.tsx`
- Modify: `frontend/src/components/ActionIcons.tsx` (append `SendIcon`)
- Modify: `frontend/src/components/NavIcons.tsx` (append `MessagesIcon`)
- Modify: `frontend/src/components/ui/BrandCard.tsx` (add `messages` mark)
- Test: `frontend/src/components/ui/Button.test.tsx` (create)

**Interfaces:**
- Produces (consumed by Tasks 7–12):
  - Types `PingRecipient`, `RequestRef {id, number, status, division_name, requestor_name, total_cost, visible}`, `PingSummary`, `PingDetail`, `DirectoryUser`, `PingCreate`.
  - Functions `pingUnreadCount(): Promise<number>`, `listPings(box): Promise<PingSummary[]>`, `getPing(id)`, `createPing(body)`, `replyToPing(id, note)`, `markPingDone(id)`, `reopenPing(id)`, `pingDirectory()`, `pingSuggestions(requestId)`.
  - `Button` accepts `size?: 'md' | 'sm'`.
  - `SendIcon(props: IconProps)` from ActionIcons; `MessagesIcon(props: NavIconProps)` from NavIcons; `PageMark` includes `'messages'`.

- [ ] **Step 1: Write the failing Button test**

Create `frontend/src/components/ui/Button.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Button } from './Button'

describe('Button size', () => {
  it('defaults to the medium padding', () => {
    render(<Button>Go</Button>)
    expect(screen.getByRole('button').className).toContain('px-4 py-2 text-sm')
  })

  it('renders a compact button for size="sm"', () => {
    render(<Button size="sm">Ping</Button>)
    const cls = screen.getByRole('button').className
    expect(cls).toContain('px-3 py-1.5 text-xs')
    expect(cls).not.toContain('px-4')
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run from `frontend/`: `node ./node_modules/vitest/vitest.mjs run src/components/ui/Button.test.tsx`
Expected: FAIL — the `sm` case still contains `px-4`.

- [ ] **Step 3: Button size prop**

Replace `frontend/src/components/ui/Button.tsx` with:

```tsx
import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'
type Size = 'md' | 'sm'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-accent-fg hover:opacity-90',
  secondary: 'border border-border bg-surface text-fg hover:bg-surface-2',
  ghost: 'text-fg hover:bg-surface-2',
}

// A prop, not a className override: two competing padding utilities resolve
// by stylesheet order, not class order, so `className="px-3"` on top of the
// default `px-4` is unreliable in Tailwind.
const SIZES: Record<Size, string> = {
  md: 'px-4 py-2 text-sm',
  sm: 'px-3 py-1.5 text-xs',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
}

export function Button({ className = '', variant = 'primary', size = 'md', ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-md font-semibold transition disabled:opacity-50 ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  )
}
```

- [ ] **Step 4: Run the Button test**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/ui/Button.test.tsx`
Expected: 2 passed.

- [ ] **Step 5: Icons and mark**

Append to `frontend/src/components/ActionIcons.tsx` (paper plane, same `Icon` wrapper):

```tsx
/* ---- messaging ---- */

export function SendIcon(props: IconProps) {
  return (
    <Icon {...props}>
      <path d="M21 3 3 10.5l7.5 3L13.5 21 21 3z" />
      <path d="M10.5 13.5 21 3" />
    </Icon>
  )
}
```

Append to `frontend/src/components/NavIcons.tsx` (speech bubble with a dot, same `Icon` wrapper):

```tsx
export function MessagesIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H9l-5 4v-4A2.5 2.5 0 0 1 4 13.5z" />
      <path d="M8 8.5h8M8 11.5h5" />
    </Icon>
  )
}
```

In `frontend/src/components/ui/BrandCard.tsx`: add `MessagesIcon` to the import from `'../NavIcons'`, add `| 'messages'` to the `PageMark` union, and `messages: MessagesIcon,` to `MARKS`.

- [ ] **Step 6: API client**

Create `frontend/src/api/pings.ts`:

```ts
import { api } from './client'

/** In-app work routing. Read state is per person; DONE is shared across the
 *  roster (server-derived), so `done_by` names whoever closed it first. */

export interface PingRecipient {
  user_id: string
  name: string
  email: string
  read_at: string | null
  completed_at: string | null
}

/** Identifying summary of the request a ping is about (spec section 4.1). It
 *  renders even when the viewer cannot open the request; `visible` is what
 *  gates the deep link, or a link that 403s reads as broken software. */
export interface RequestRef {
  id: string
  number: string
  status: string
  division_name: string | null
  requestor_name: string | null
  total_cost: string | null
  visible: boolean
}

export interface PingSummary {
  id: string
  note: string
  sender: { id: string; name: string }
  created_at: string
  request_id: string | null
  request: RequestRef | null
  recipients: PingRecipient[]
  reply_count: number
  unread_replies: number
  unread_for_me: boolean
  last_activity_at: string
  completed_at: string | null
  done_by: string | null
  /** Every reply's note, concatenated -- what search reaches beyond the root
   *  note and the sender/recipient names. */
  search_blob: string
}

export interface PingDetail extends PingSummary {
  replies: {
    id: string
    note: string
    created_at: string
    sender: { id: string; name: string }
  }[]
}

export interface DirectoryUser {
  id: string
  name: string
  email: string
  roles: string[]
  division_name: string | null
}

export interface PingCreate {
  recipient_ids: string[]
  note: string
  request_id?: string | null
}

export async function pingUnreadCount(): Promise<number> {
  const res = await api<{ count: number }>('/pings/unread_count')
  return res.count
}

export async function listPings(box: 'inbox' | 'sent'): Promise<PingSummary[]> {
  const res = await api<{ pings: PingSummary[] }>(`/pings?box=${box}`)
  return res.pings
}

export async function getPing(id: string): Promise<PingDetail> {
  const res = await api<{ ping: PingDetail }>(`/pings/${id}`)
  return res.ping
}

export async function createPing(body: PingCreate): Promise<PingDetail> {
  const res = await api<{ ping: PingDetail }>('/pings', { method: 'POST', body })
  return res.ping
}

export async function replyToPing(id: string, note: string): Promise<PingDetail> {
  const res = await api<{ ping: PingDetail }>(`/pings/${id}/reply`, {
    method: 'POST',
    body: { note },
  })
  return res.ping
}

export async function markPingDone(id: string): Promise<PingDetail> {
  const res = await api<{ ping: PingDetail }>(`/pings/${id}/done`, { method: 'POST' })
  return res.ping
}

export async function reopenPing(id: string): Promise<PingDetail> {
  const res = await api<{ ping: PingDetail }>(`/pings/${id}/reopen`, { method: 'POST' })
  return res.ping
}

export async function pingDirectory(): Promise<DirectoryUser[]> {
  const res = await api<{ users: DirectoryUser[] }>('/pings/directory')
  return res.users
}

/** The requestor plus, when pending, the current level's eligible approvers
 *  (FINANCE once approved) -- ranked first in the New Ping modal. */
export async function pingSuggestions(requestId: string): Promise<DirectoryUser[]> {
  const res = await api<{ users: DirectoryUser[] }>(
    `/pings/suggestions?request_id=${encodeURIComponent(requestId)}`,
  )
  return res.users
}
```

- [ ] **Step 7: Typecheck and run all frontend tests**

Run: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` then `node ./node_modules/vitest/vitest.mjs run`
Expected: no type errors; all tests pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/pings.ts frontend/src/components/ui/Button.tsx frontend/src/components/ui/Button.test.tsx frontend/src/components/ActionIcons.tsx frontend/src/components/NavIcons.tsx frontend/src/components/ui/BrandCard.tsx
git commit -m "feat(pings): typed API client, Button size prop, Send and Messages icons"
```

---

### Task 7: The header bell

**Files:**
- Create: `frontend/src/components/PingBell.tsx`, `frontend/src/components/PingBell.test.tsx`
- Modify: `frontend/src/components/AppShell.tsx` (header only; the panel wiring lands in Task 10)

**Interfaces:**
- Consumes: `pingUnreadCount` (Task 6).
- Produces: `PingBell({ onClick }: { onClick: () => void })`, query key `['pings', 'unread']`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/PingBell.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PingBell } from './PingBell'

vi.mock('../api/pings', () => ({ pingUnreadCount: vi.fn() }))
import { pingUnreadCount } from '../api/pings'

function renderBell() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <PingBell onClick={() => {}} />
    </QueryClientProvider>,
  )
}

describe('PingBell', () => {
  it('shows the unread count', async () => {
    vi.mocked(pingUnreadCount).mockResolvedValue(3)
    renderBell()
    expect(await screen.findByText('3')).toBeInTheDocument()
  })

  it('caps the badge at 99+', async () => {
    vi.mocked(pingUnreadCount).mockResolvedValue(120)
    renderBell()
    expect(await screen.findByText('99+')).toBeInTheDocument()
  })

  it('shows no badge at zero', async () => {
    vi.mocked(pingUnreadCount).mockResolvedValue(0)
    renderBell()
    expect(await screen.findByRole('button', { name: /messages/i })).toBeInTheDocument()
    expect(screen.queryByTestId('ping-badge')).toBeNull()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/PingBell.test.tsx`
Expected: FAIL — cannot resolve `./PingBell`.

- [ ] **Step 3: Implement the bell**

Create `frontend/src/components/PingBell.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'

import { pingUnreadCount } from '../api/pings'

/** The 🔔 emoji is a deliberate exception to the custom-icon rule (spec
 *  section 8.2): the yellow bell is the recognisable affordance across ARIA,
 *  SCORE and CAPRI, and users move between the apps.
 *
 *  The count polls on a TanStack interval -- invalidate ['pings'] after any
 *  action and the badge updates at once instead of up to 30s later. */
export function PingBell({ onClick }: { onClick: () => void }) {
  const { data: unread = 0 } = useQuery({
    queryKey: ['pings', 'unread'],
    queryFn: pingUnreadCount,
    refetchInterval: 30_000,
  })

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Messages"
      title="Messages"
      className="relative rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm hover:bg-surface-2"
    >
      🔔
      {unread > 0 && (
        <span
          data-testid="ping-badge"
          className="absolute -right-2 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white tabular-nums"
        >
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </button>
  )
}
```

- [ ] **Step 4: Run the test**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/PingBell.test.tsx`
Expected: 3 passed.

- [ ] **Step 5: Place the bell in the header**

In `frontend/src/components/AppShell.tsx`: import `{ useState } from 'react'` and `{ PingBell } from './PingBell'`. Inside `AppShell`, add `const [pingsOpen, setPingsOpen] = useState(false)`. In the header's right-hand `div`, insert `<PingBell onClick={() => setPingsOpen(true)} />` between `{user?.name}` and `<ThemeToggle />`. (`pingsOpen` is read by the panel in Task 10; until then `tsc` may warn it is unused only if `noUnusedLocals` is on — if so, render `{pingsOpen && null}` temporarily and remove it in Task 10.)

- [ ] **Step 6: Typecheck, build, and look at it**

Run: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, then `node ./node_modules/vite/bin/vite.js build`, then start the backend (`flask run --port 5100` from `backend/` with the venv active) and open `http://localhost:5100` as `admin@uniteduptime.com / ChangeMe123!`.
Expected: the bell sits left of the theme toggle with no badge (no pings yet). Ask the user to confirm visually.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PingBell.tsx frontend/src/components/PingBell.test.tsx frontend/src/components/AppShell.tsx
git commit -m "feat(pings): header bell polling the unread count"
```

---

### Task 8: PingCard and PingDetail

**Files:**
- Create: `frontend/src/components/PingCard.tsx`, `frontend/src/components/PingDetail.tsx`, `frontend/src/components/PingDetail.test.tsx`

**Interfaces:**
- Consumes: `getPing`, `replyToPing`, `markPingDone`, `reopenPing`, types (Task 6); `useMe` (`data.id`); `formatActionDate` from `routes/formatDate`; `StatusBadge` from `ui/Badge`.
- Produces:
  - `statusOf(ping): 'unread' | 'read' | 'done'`, `PingStatusPill({ ping })`, `PingCard({ ping, onOpen })` from PingCard.
  - `PingDetail({ id, onBack?, onNavigate? })` — renders the thread; `onNavigate` fires when the request link is followed so a hosting overlay can close.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/PingDetail.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { PingDetail } from './PingDetail'
import type { PingDetail as PingDetailType } from '../api/pings'

vi.mock('../api/pings', () => ({
  getPing: vi.fn(),
  replyToPing: vi.fn(),
  markPingDone: vi.fn(),
  reopenPing: vi.fn(),
}))
import { getPing, replyToPing, markPingDone, reopenPing } from '../api/pings'

vi.mock('../auth/useMe', () => ({
  useMe: () => ({ data: { id: 'u1', name: 'Me', email: 'me@x.com', roles: ['APPROVER'],
                          division_id: null, must_change_password: false } }),
}))

function baseDetail(overrides: Partial<PingDetailType> = {}): PingDetailType {
  return {
    id: 'p1',
    note: 'Please confirm the GL account.',
    sender: { id: 'u2', name: 'Sam Sender' },
    created_at: '2026-09-09T12:00:00+00:00',
    request_id: null,
    request: null,
    recipients: [
      { user_id: 'u1', name: 'Me', email: 'me@x.com', read_at: null, completed_at: null },
      { user_id: 'u3', name: 'Ann', email: 'a@x.com', read_at: null, completed_at: null },
    ],
    reply_count: 1,
    unread_replies: 0,
    unread_for_me: false,
    last_activity_at: '2026-09-09T12:05:00+00:00',
    completed_at: null,
    done_by: null,
    search_blob: 'Looking now.',
    replies: [
      { id: 'r1', note: 'Looking now.', created_at: '2026-09-09T12:05:00+00:00',
        sender: { id: 'u3', name: 'Ann' } },
    ],
    ...overrides,
  }
}

const REQ = {
  id: 'req-1', number: 'CX000042', status: 'PENDING_L1', division_name: '100 — Ops',
  requestor_name: 'Owner', total_cost: '30000', visible: true,
}

function renderDetail(props: Partial<Parameters<typeof PingDetail>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <PingDetail id="p1" {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PingDetail', () => {
  it('renders the note, replies and roster', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail())
    renderDetail()
    expect(await screen.findByText('Please confirm the GL account.')).toBeInTheDocument()
    expect(screen.getByText('Looking now.')).toBeInTheDocument()
    expect(screen.getByText('Sam Sender')).toBeInTheDocument()
    expect(screen.getAllByText('Ann').length).toBeGreaterThan(0)
  })

  it('renders the request chip as a link when visible, and fires onNavigate', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail({ request_id: 'req-1', request: REQ }))
    const onNavigate = vi.fn()
    renderDetail({ onNavigate })
    const link = await screen.findByRole('link', { name: /CX000042/ })
    expect(link).toHaveAttribute('href', '/requests/req-1')
    expect(screen.getByText('Pending L1')).toBeInTheDocument()
    fireEvent.click(link)
    expect(onNavigate).toHaveBeenCalled()
  })

  it('renders the request chip as plain text when not visible', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail({
      request_id: 'req-1', request: { ...REQ, visible: false },
    }))
    renderDetail()
    await screen.findByText(/CX000042/)
    expect(screen.queryByRole('link', { name: /CX000042/ })).toBeNull()
  })

  it('Send calls replyToPing with the typed note', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail())
    vi.mocked(replyToPing).mockResolvedValue(baseDetail())
    renderDetail()
    await screen.findByText('Please confirm the GL account.')
    fireEvent.change(screen.getByPlaceholderText(/reply/i), { target: { value: 'On it.' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    await waitFor(() => expect(replyToPing).toHaveBeenCalledWith('p1', 'On it.'))
  })

  it('Mark done calls markPingDone when the viewer is on the roster', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail())
    vi.mocked(markPingDone).mockResolvedValue(baseDetail())
    renderDetail()
    await screen.findByText('Please confirm the GL account.')
    fireEvent.click(screen.getByRole('button', { name: /mark done/i }))
    await waitFor(() => expect(markPingDone).toHaveBeenCalledWith('p1'))
  })

  it('offers neither Mark done nor Reopen when the viewer is off the roster', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail({
      recipients: [{ user_id: 'u3', name: 'Ann', email: 'a@x.com', read_at: null, completed_at: null }],
    }))
    renderDetail()
    await screen.findByText('Please confirm the GL account.')
    expect(screen.queryByRole('button', { name: /mark done/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /^reopen$/i })).toBeNull()
  })

  it('offers Reopen and shows Done by once the viewer has ticked it', async () => {
    vi.mocked(getPing).mockResolvedValue(baseDetail({
      completed_at: '2026-09-09T13:00:00+00:00',
      done_by: 'Me',
      recipients: [
        { user_id: 'u1', name: 'Me', email: 'me@x.com', read_at: null,
          completed_at: '2026-09-09T13:00:00+00:00' },
      ],
    }))
    vi.mocked(reopenPing).mockResolvedValue(baseDetail())
    renderDetail()
    await screen.findByText('Please confirm the GL account.')
    expect(screen.getByText(/Done by Me/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^reopen$/i }))
    await waitFor(() => expect(reopenPing).toHaveBeenCalledWith('p1'))
  })

  it('renders an error with the back button still usable when the fetch fails', async () => {
    vi.mocked(getPing).mockRejectedValue(new Error('boom'))
    const onBack = vi.fn()
    renderDetail({ onBack })
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /back/i }))
    expect(onBack).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/PingDetail.test.tsx`
Expected: FAIL — cannot resolve `./PingDetail`.

- [ ] **Step 3: PingCard**

Create `frontend/src/components/PingCard.tsx`:

```tsx
import type { PingSummary } from '../api/pings'
import { formatActionDate } from '../routes/formatDate'

const PILL: Record<string, string> = {
  unread: 'text-accent border-accent',
  read: 'text-muted border-muted',
  done: 'text-green-700 border-green-700 dark:text-green-400 dark:border-green-400',
}

export function statusOf(ping: PingSummary): 'unread' | 'read' | 'done' {
  if (ping.completed_at) return 'done'
  return ping.unread_for_me ? 'unread' : 'read'
}

/** Status pills are OUTLINED, never filled -- three filled blocks compete with
 *  the table they sit in (spec section 8.8). */
export function PingStatusPill({ ping }: { ping: PingSummary }) {
  const status = statusOf(ping)
  return (
    <span className={`inline-block rounded-lg border px-1.5 py-px text-[10px] font-bold ${PILL[status]}`}>
      {status}
    </span>
  )
}

export function PingCard({ ping, onOpen }: { ping: PingSummary; onOpen: () => void }) {
  const who =
    ping.recipients.length > 2
      ? `${ping.recipients.slice(0, 2).map((r) => r.name).join(', ')} +${ping.recipients.length - 2}`
      : ping.recipients.map((r) => r.name).join(', ')

  return (
    <button
      type="button"
      onClick={onOpen}
      className={`mb-2 w-full rounded-lg border p-3 text-left ${
        ping.unread_for_me ? 'border-accent bg-accent/5' : 'border-border bg-surface'
      }`}
    >
      <div className="mb-1 flex items-center gap-2">
        <span className="flex-1 truncate text-xs font-bold">{ping.sender.name || who}</span>
        <span className="whitespace-nowrap text-[10px] text-muted">{formatActionDate(ping.last_activity_at)}</span>
        <PingStatusPill ping={ping} />
      </div>
      <div className="text-xs leading-relaxed text-fg/80">{ping.note}</div>
      {ping.request && (
        <div className="mt-1 text-[10px] text-muted">{ping.request.number}</div>
      )}
      {ping.done_by && <div className="mt-1.5 text-[10px] text-muted">Done by {ping.done_by}</div>}
    </button>
  )
}
```

- [ ] **Step 4: PingDetail**

Create `frontend/src/components/PingDetail.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { useMe } from '../auth/useMe'
import { getPing, markPingDone, replyToPing, reopenPing } from '../api/pings'
import { formatActionDate } from '../routes/formatDate'
import { StatusBadge } from './ui/Badge'

const CHIP = 'inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-[11px] text-muted'

/** The ping detail view: the note, the request it is about, the roster,
 *  replies, a reply box, and Done/Reopen. Hosted by PingPanel (slide-over) and
 *  MessagesPage (inline row expansion). */
export function PingDetail({ id, onBack, onNavigate }: {
  id: string
  onBack?: () => void
  /** Fired when the request link is followed, so a hosting overlay can close
   *  itself instead of sitting over the page it just navigated to. */
  onNavigate?: () => void
}) {
  const queryClient = useQueryClient()
  const me = useMe()
  const [note, setNote] = useState('')

  const { data: ping, isError } = useQuery({
    queryKey: ['pings', 'detail', id],
    queryFn: () => getPing(id),
  })

  // Fetching the detail is what stamps read server-side, so the bell and the
  // list must catch up -- once per successful load, not on every render, or a
  // reply's own refetch of this query would re-fire it forever.
  const invalidatedFor = useRef<string | null>(null)
  useEffect(() => {
    if (ping && invalidatedFor.current !== ping.id) {
      invalidatedFor.current = ping.id
      queryClient.invalidateQueries({ queryKey: ['pings', 'unread'] })
      queryClient.invalidateQueries({ queryKey: ['pings', 'list'] })
    }
  }, [ping, queryClient])

  function afterAction() {
    queryClient.invalidateQueries({ queryKey: ['pings'] })
  }

  const replyMutation = useMutation({
    mutationFn: (text: string) => replyToPing(id, text),
    onSuccess: () => { setNote(''); afterAction() },
  })
  const doneMutation = useMutation({ mutationFn: () => markPingDone(id), onSuccess: afterAction })
  const reopenMutation = useMutation({ mutationFn: () => reopenPing(id), onSuccess: afterAction })

  const back = onBack && (
    <button type="button" onClick={onBack}
      className="mb-3 self-start text-xs font-semibold text-muted hover:text-fg">
      ← Back
    </button>
  )

  if (isError) {
    return (
      <div className="flex flex-1 flex-col p-3 text-sm">
        {back}
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">Could not load this ping.</p>
      </div>
    )
  }
  if (!ping) return <p className="p-3 text-xs text-muted">Loading…</p>

  const mine = ping.recipients.find((r) => r.user_id === me.data?.id)
  const trimmed = note.trim()
  const req = ping.request

  return (
    <div className="flex flex-1 flex-col overflow-y-auto p-3 text-sm">
      {back}

      <div className="mb-1 flex items-center gap-2">
        <span className="text-xs font-bold">{ping.sender.name}</span>
        <span className="text-[10px] text-muted">{formatActionDate(ping.created_at)}</span>
      </div>
      <p className="mb-3 whitespace-pre-wrap text-sm leading-relaxed">{ping.note}</p>

      {req && (
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          {req.visible ? (
            <Link to={`/requests/${req.id}`} onClick={onNavigate}
              className="inline-flex items-center gap-1.5 rounded-full border border-accent px-2 py-0.5 text-[11px] text-accent">
              {req.number} <StatusBadge status={req.status} />
            </Link>
          ) : (
            <span className={CHIP}>{req.number} <StatusBadge status={req.status} /></span>
          )}
          <span className="text-[11px] text-muted">
            {req.requestor_name ?? '—'} · {req.division_name ?? '—'} · ${Number(req.total_cost ?? 0).toLocaleString()}
          </span>
        </div>
      )}

      <div className="mb-3 border-t border-border pt-2">
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted">Roster</div>
        {ping.recipients.map((r) => (
          <div key={r.user_id} className="flex items-center justify-between py-0.5 text-xs">
            <span>{r.name}</span>
            <span className="text-muted">{r.completed_at ? 'done' : r.read_at ? 'read' : ''}</span>
          </div>
        ))}
      </div>

      {ping.replies.length > 0 && (
        <div className="mb-3 border-t border-border pt-2">
          {ping.replies.map((r) => (
            <div key={r.id} className="mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold">{r.sender.name}</span>
                <span className="text-[10px] text-muted">{formatActionDate(r.created_at)}</span>
              </div>
              <p className="whitespace-pre-wrap text-xs leading-relaxed text-fg/80">{r.note}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-auto border-t border-border pt-2">
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          placeholder="Reply…"
          className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-xs outline-none placeholder:text-muted focus:border-accent"
        />
        <div className="mt-2 flex items-center justify-between gap-2">
          <button
            type="button"
            disabled={!trimmed || replyMutation.isPending}
            onClick={() => trimmed && replyMutation.mutate(trimmed)}
            className="rounded-md bg-accent px-2.5 py-1 text-xs font-semibold text-accent-fg disabled:opacity-50"
          >
            Send
          </button>
          <div className="flex items-center gap-2">
            {ping.done_by && <span className="text-[10px] text-muted">Done by {ping.done_by}</span>}
            {mine && (mine.completed_at ? (
              <button type="button" onClick={() => reopenMutation.mutate()}
                className="text-xs font-semibold text-muted hover:text-fg">Reopen</button>
            ) : (
              <button type="button" onClick={() => doneMutation.mutate()}
                className="text-xs font-semibold text-accent">Mark done</button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Run the tests**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/PingDetail.test.tsx`
Expected: 8 passed. If the "Pending L1" assertion finds two matches (one inside the link, one in the chip), the visible/invisible branches are both rendering — check the `req.visible` ternary.

- [ ] **Step 6: Typecheck and commit**

Run: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` — expected clean.

```bash
git add frontend/src/components/PingCard.tsx frontend/src/components/PingDetail.tsx frontend/src/components/PingDetail.test.tsx
git commit -m "feat(pings): PingCard and PingDetail with request chip, roster, replies, done/reopen"
```

---

### Task 9: The New Ping modal

**Files:**
- Create: `frontend/src/components/PingModal.tsx`, `frontend/src/components/PingModal.test.tsx`

**Interfaces:**
- Consumes: `createPing`, `pingDirectory`, `pingSuggestions`, `DirectoryUser`, `RequestRef` (Task 6); `SendIcon`; `Button`.
- Produces: `PingInit { recipientIds?: string[]; request?: { id: string; number: string } | null }` and `PingModal({ init, onClose })`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/PingModal.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { DirectoryUser, PingDetail } from '../api/pings'
import { PingModal } from './PingModal'

vi.mock('../api/pings', () => ({
  createPing: vi.fn(),
  pingDirectory: vi.fn(),
  pingSuggestions: vi.fn(),
}))
import { createPing, pingDirectory, pingSuggestions } from '../api/pings'

const USERS: DirectoryUser[] = [
  { id: 'u1', name: 'Dana Whitfield', email: 'dana@x.com', roles: ['FINANCE'], division_name: null },
  { id: 'u2', name: 'Ann Reader', email: 'ann@x.com', roles: ['APPROVER'], division_name: '100 — Ops' },
]

function detailStub(): PingDetail {
  return {
    id: 'p1', note: 'x', sender: { id: 'u9', name: 'Me' },
    created_at: '2026-09-09T12:00:00+00:00', request_id: null, request: null,
    recipients: [], reply_count: 0, unread_replies: 0, unread_for_me: false,
    last_activity_at: '2026-09-09T12:00:00+00:00', completed_at: null, done_by: null,
    search_blob: '', replies: [],
  }
}

function renderModal(init: Parameters<typeof PingModal>[0]['init'] = {}, onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <PingModal init={init} onClose={onClose} />
    </QueryClientProvider>,
  )
  return onClose
}

const noteBox = () => screen.getAllByRole('textbox').find((el) => el.tagName === 'TEXTAREA')!

describe('PingModal', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the directory and counts a checked recipient toward N/25', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    renderModal()
    expect(await screen.findByText('Dana Whitfield')).toBeInTheDocument()
    expect(screen.getByText('0/25 recipients')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    expect(screen.getByText('1/25 recipients')).toBeInTheDocument()
  })

  it('disables Send with no note or no recipients', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    renderModal()
    await screen.findByText('Dana Whitfield')
    const send = screen.getByRole('button', { name: /^send$/i })
    expect(send).toBeDisabled()
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    expect(send).toBeDisabled()                       // recipient, no note
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    fireEvent.change(noteBox(), { target: { value: 'hi' } })
    expect(send).toBeDisabled()                       // note, no recipient
  })

  it('Send posts the picked recipients, note and request id, then closes', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    vi.mocked(pingSuggestions).mockResolvedValue([])
    vi.mocked(createPing).mockResolvedValue(detailStub())
    const onClose = renderModal({ request: { id: 'req-1', number: 'CX000042' } })
    await screen.findByText('Dana Whitfield')
    expect(screen.getByText('CX000042')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('checkbox', { name: /dana whitfield/i }))
    fireEvent.change(noteBox(), { target: { value: 'Please take a look' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    await waitFor(() => expect(createPing).toHaveBeenCalledWith({
      recipient_ids: ['u1'], note: 'Please take a look', request_id: 'req-1',
    }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('clearing the request chip sends request_id null', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    vi.mocked(pingSuggestions).mockResolvedValue([])
    vi.mocked(createPing).mockResolvedValue(detailStub())
    renderModal({ request: { id: 'req-1', number: 'CX000042' } })
    await screen.findByText('CX000042')
    fireEvent.click(screen.getByRole('button', { name: /remove request/i }))
    expect(screen.queryByText('CX000042')).toBeNull()
    fireEvent.click(screen.getByRole('checkbox', { name: /dana whitfield/i }))
    fireEvent.change(noteBox(), { target: { value: 'General question' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    await waitFor(() => expect(createPing).toHaveBeenCalledWith(
      expect.objectContaining({ request_id: null })))
  })

  it('with a request, suggested users render first under Suggested and only once', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    vi.mocked(pingSuggestions).mockResolvedValue([USERS[1]])
    renderModal({ request: { id: 'req-1', number: 'CX000042' } })
    expect(await screen.findByText('Suggested')).toBeInTheDocument()
    expect(pingSuggestions).toHaveBeenCalledWith('req-1')
    const rows = screen.getAllByRole('checkbox').map((el) => el.closest('label'))
    expect(screen.getAllByText('Ann Reader')).toHaveLength(1)
    const ann = rows.find((r) => r?.textContent?.includes('Ann Reader'))
    const dana = rows.find((r) => r?.textContent?.includes('Dana Whitfield'))
    expect(rows.indexOf(ann!)).toBeLessThan(rows.indexOf(dana!))
  })

  it('without a request, pingSuggestions is never called', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    renderModal()
    await screen.findByText('Dana Whitfield')
    expect(pingSuggestions).not.toHaveBeenCalled()
  })

  it('shows the server error when Send fails', async () => {
    vi.mocked(pingDirectory).mockResolvedValue(USERS)
    vi.mocked(createPing).mockRejectedValue(new Error('A ping needs a note.'))
    renderModal()
    await screen.findByText('Dana Whitfield')
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    fireEvent.change(noteBox(), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('A ping needs a note.')
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/PingModal.test.tsx`
Expected: FAIL — cannot resolve `./PingModal`.

- [ ] **Step 3: Implement the modal**

Create `frontend/src/components/PingModal.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { createPing, pingDirectory, pingSuggestions, type DirectoryUser } from '../api/pings'
import { Button } from './ui/Button'
import { SendIcon } from './ActionIcons'

export interface PingInit {
  recipientIds?: string[]
  /** The request this ping is about; the chip shows the number and can be cleared. */
  request?: { id: string; number: string } | null
}

const MAX_RECIPIENTS = 25 // mirrors ping_service.MAX_RECIPIENTS

/** One shared modal behind every entry point (spec section 8.5); an entry
 *  point differs only in the `init` it passes. */
export function PingModal({ init, onClose }: { init: PingInit; onClose: () => void }) {
  const qc = useQueryClient()
  const [selected, setSelected] = useState<string[]>(init.recipientIds ?? [])
  const [request, setRequest] = useState(init.request ?? null)
  const [note, setNote] = useState('')
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  const { data: users = [] } = useQuery({ queryKey: ['pings', 'directory'], queryFn: pingDirectory })
  const { data: suggested = [] } = useQuery({
    queryKey: ['pings', 'suggestions', request?.id],
    queryFn: () => pingSuggestions(request!.id),
    enabled: !!request,
  })

  const send = useMutation({
    mutationFn: () => createPing({ recipient_ids: selected, note, request_id: request?.id ?? null }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['pings'] }); onClose() },
    onError: (err: Error) => setError(err.message),
  })

  const term = search.trim().toLowerCase()
  const matches = (u: DirectoryUser) => u.name.toLowerCase().includes(term)
  const suggestedShown = term ? suggested.filter(matches) : suggested
  const suggestedIds = new Set(suggested.map((u) => u.id))
  const rest = users.filter((u) => !suggestedIds.has(u.id))
  const shown = term ? rest.filter(matches) : rest

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))

  return (
    <div className="fixed inset-0 z-[1500] flex items-center justify-center bg-black/50 p-4">
      <div role="dialog" aria-modal="true" aria-label="New ping"
        className="flex max-h-[80vh] w-[520px] max-w-full flex-col rounded-lg border border-border bg-surface">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3">
          <span className="flex-1 text-sm font-bold">🔔 New Ping</span>
          <button type="button" onClick={onClose} aria-label="Close" className="text-muted">✕</button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted">To</label>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search people…"
            className="mb-2 w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm" />
          <div className="mb-4 max-h-40 overflow-y-auto rounded-md border border-border">
            {suggestedShown.length > 0 && (
              <>
                <div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-muted">Suggested</div>
                {suggestedShown.map((u) => <UserRow key={u.id} user={u} selected={selected} toggle={toggle} />)}
              </>
            )}
            {shown.map((u) => <UserRow key={u.id} user={u} selected={selected} toggle={toggle} />)}
          </div>

          {request && (
            <>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted">Request</label>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border px-2.5 py-0.5 text-xs">
                <span>{request.number}</span>
                <button type="button" onClick={() => setRequest(null)} aria-label="Remove request"
                  className="text-muted hover:text-fg">✕</button>
              </div>
            </>
          )}

          <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted">Note</label>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={5}
            className="w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm" />

          {error && <p role="alert" className="mt-2 text-xs text-red-700 dark:text-red-300">{error}</p>}
        </div>

        <footer className="flex items-center gap-2 border-t border-border px-4 py-3">
          <span className="flex-1 text-xs text-muted tabular-nums">{selected.length}/{MAX_RECIPIENTS} recipients</span>
          <Button variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" disabled={send.isPending || !note.trim() || selected.length === 0}
            onClick={() => send.mutate()}>
            <SendIcon size={14} />
            {send.isPending ? 'Sending…' : 'Send'}
          </Button>
        </footer>
      </div>
    </div>
  )
}

function UserRow({ user, selected, toggle }: {
  user: DirectoryUser; selected: string[]; toggle: (id: string) => void
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 px-2 py-1 text-sm hover:bg-surface-2">
      <input type="checkbox" checked={selected.includes(user.id)} onChange={() => toggle(user.id)} />
      <span className="flex-1">{user.name}</span>
      <span className="text-xs text-muted">{user.roles.join(', ')}</span>
    </label>
  )
}
```

- [ ] **Step 4: Run the tests**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/PingModal.test.tsx`
Expected: 7 passed.

- [ ] **Step 5: Typecheck and commit**

Run: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` — expected clean.

```bash
git add frontend/src/components/PingModal.tsx frontend/src/components/PingModal.test.tsx
git commit -m "feat(pings): New Ping modal with suggested-first directory and request chip"
```

---

### Task 10: The slide-over panel, wired to the bell

**Files:**
- Create: `frontend/src/components/PingPanel.tsx`, `frontend/src/components/PingPanel.test.tsx`
- Modify: `frontend/src/components/AppShell.tsx`

**Interfaces:**
- Consumes: `listPings`, `PingSummary` (Task 6); `PingCard`, `statusOf` (Task 8); `PingDetail` (Task 8); `PingModal`, `PingInit` (Task 9); `Button`, `SendIcon`.
- Produces: `PingPanel({ onClose })`; exports `haystack(ping): string`, `matches(ping, filter): boolean`, `FILTERS`, type `Filter` for the Messages page (Task 11).

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/PingPanel.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PingSummary } from '../api/pings'
import { PingPanel } from './PingPanel'

vi.mock('../api/pings', () => ({
  listPings: vi.fn(), getPing: vi.fn(), replyToPing: vi.fn(), markPingDone: vi.fn(),
  reopenPing: vi.fn(), createPing: vi.fn(), pingDirectory: vi.fn(), pingSuggestions: vi.fn(),
}))
import { listPings, getPing } from '../api/pings'
vi.mock('../auth/useMe', () => ({
  useMe: () => ({ data: { id: 'u2', name: 'Ann', email: 'a@x.com', roles: ['APPROVER'],
                          division_id: null, must_change_password: false } }),
}))

function makePing(overrides: Partial<PingSummary> = {}): PingSummary {
  return {
    id: 'p1', note: 'Root note about the forklift.', sender: { id: 'u1', name: 'Sam Sender' },
    created_at: '2026-09-09T12:00:00+00:00', request_id: null, request: null,
    recipients: [{ user_id: 'u2', name: 'Ann', email: 'a@x.com', read_at: null, completed_at: null }],
    reply_count: 1, unread_replies: 0, unread_for_me: false,
    last_activity_at: '2026-09-09T12:05:00+00:00', completed_at: null, done_by: null,
    search_blob: '', ...overrides,
  }
}

function renderPanel(onClose: () => void = () => {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><PingPanel onClose={onClose} /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PingPanel', () => {
  it('lists inbox cards and switches to Sent', async () => {
    vi.mocked(listPings).mockResolvedValue([makePing()])
    renderPanel()
    expect(await screen.findByText('Root note about the forklift.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^sent$/i }))
    expect(listPings).toHaveBeenCalledWith('sent')
  })

  it('finds a conversation by a phrase said only in a reply', async () => {
    vi.mocked(listPings).mockResolvedValue([
      makePing({ id: 'p1', search_blob: 'the phrase nobody else says' }),
      makePing({ id: 'p2', note: 'Unrelated ping.' }),
    ])
    renderPanel()
    await screen.findByText('Root note about the forklift.')
    fireEvent.change(screen.getByLabelText(/search messages/i), { target: { value: 'nobody else says' } })
    expect(screen.getByText('Root note about the forklift.')).toBeInTheDocument()
    expect(screen.queryByText('Unrelated ping.')).toBeNull()
  })

  it('the Open filter hides done pings and the Done chip counts them', async () => {
    vi.mocked(listPings).mockResolvedValue([
      makePing({ id: 'p1' }),
      makePing({ id: 'p2', note: 'Finished one.', completed_at: '2026-09-09T13:00:00+00:00', done_by: 'Ann' }),
    ])
    renderPanel()
    await screen.findByText('Root note about the forklift.')
    expect(screen.queryByText('Finished one.')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /^done/i }))
    expect(screen.getByText('Finished one.')).toBeInTheDocument()
  })

  it('closes the panel when the detail\'s request link is followed', async () => {
    vi.mocked(listPings).mockResolvedValue([makePing({ request_id: 'req-1' })])
    vi.mocked(getPing).mockResolvedValue({
      ...makePing({ request_id: 'req-1' }), replies: [],
      request: { id: 'req-1', number: 'CX000042', status: 'DRAFT', division_name: null,
                 requestor_name: 'Owner', total_cost: '0', visible: true },
    })
    const onClose = vi.fn()
    renderPanel(onClose)
    fireEvent.click(await screen.findByText('Root note about the forklift.'))
    fireEvent.click(await screen.findByRole('link', { name: /CX000042/ }))
    expect(onClose).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/PingPanel.test.tsx`
Expected: FAIL — cannot resolve `./PingPanel`.

- [ ] **Step 3: Implement the panel**

Create `frontend/src/components/PingPanel.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { listPings, type PingSummary } from '../api/pings'
import { Button } from './ui/Button'
import { SendIcon } from './ActionIcons'
import { PingCard, statusOf } from './PingCard'
import { PingDetail } from './PingDetail'
import { PingModal, type PingInit } from './PingModal'

export type Box = 'inbox' | 'sent'
export type Filter = 'open' | 'unread' | 'read' | 'done'

export const FILTERS: [Filter, string][] = [
  ['open', 'Open'], ['unread', 'Unread'], ['read', 'Read'], ['done', 'Done'],
]

export function matches(ping: PingSummary, filter: Filter): boolean {
  return filter === 'open' ? statusOf(ping) !== 'done' : statusOf(ping) === filter
}

/** Search covers sender, recipients, the request number, the note and every
 *  REPLY's text (the server's search_blob). */
export function haystack(ping: PingSummary): string {
  return [ping.note, ping.sender.name, ...ping.recipients.map((r) => r.name),
          ping.request?.number, ping.search_blob]
    .filter(Boolean).join(' ').toLowerCase()
}

/** Filter chips shared by the panel and the Messages page. */
export function FilterChips({ pings, filter, onChange }: {
  pings: PingSummary[]; filter: Filter; onChange: (f: Filter) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {FILTERS.map(([key, label]) => {
        const count = pings.filter((p) => matches(p, key)).length
        const on = filter === key
        return (
          <button key={key} type="button" onClick={() => onChange(key)}
            className={`rounded-full border px-2.5 py-0.5 text-xs ${
              on ? 'border-accent bg-accent/10 font-semibold text-accent' : 'border-border text-muted'}`}>
            {label}
            {count > 0 && <span className="ml-1.5 opacity-75 tabular-nums">{count}</span>}
          </button>
        )
      })}
    </div>
  )
}

/** The bell's quick view: 440px, right-anchored, light surface (spec section 8.4). */
export function PingPanel({ onClose }: { onClose: () => void }) {
  const [box, setBox] = useState<Box>('inbox')
  const [filter, setFilter] = useState<Filter>('open')
  const [search, setSearch] = useState('')
  const [openId, setOpenId] = useState<string | null>(null)
  const [composing, setComposing] = useState<PingInit | null>(null)

  const { data: pings = [] } = useQuery({ queryKey: ['pings', 'list', box], queryFn: () => listPings(box) })

  const term = search.trim().toLowerCase()
  const searched = term ? pings.filter((p) => haystack(p).includes(term)) : pings
  const shown = searched.filter((p) => matches(p, filter))

  return (
    <div className="fixed inset-0 z-[1100] bg-black/50"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <aside role="dialog" aria-modal="true" aria-label="Messages"
        className="absolute inset-y-0 right-0 flex w-[440px] max-w-full flex-col border-l border-border bg-surface text-fg">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3">
          <span className="flex-1 text-sm font-bold">🔔 Messages</span>
          <Button size="sm" onClick={() => setComposing({})}><SendIcon size={14} />New Ping</Button>
          <button type="button" onClick={onClose} aria-label="Close" className="text-muted">✕</button>
        </header>

        <div className="flex border-b border-border">
          {(['inbox', 'sent'] as Box[]).map((key) => (
            <button key={key} type="button" onClick={() => { setBox(key); setOpenId(null) }}
              className={`flex-1 border-b-2 py-2 text-xs font-bold capitalize ${
                box === key ? 'border-accent text-fg' : 'border-transparent text-muted'}`}>
              {key}
            </button>
          ))}
        </div>

        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Search person, request or words…" aria-label="Search messages"
          className="mx-3 mt-3 rounded-md border border-border bg-surface px-2 py-1.5 text-xs" />
        <div className="px-3 pt-2.5">
          <FilterChips pings={searched} filter={filter} onChange={setFilter} />
        </div>

        {openId ? (
          /* Following the request link closes the whole panel -- it must not
             sit over the page it just navigated to. */
          <PingDetail id={openId} onBack={() => setOpenId(null)} onNavigate={onClose} />
        ) : (
          <div className="flex-1 overflow-y-auto p-3">
            {shown.length === 0
              ? <p className="p-3 text-xs text-muted">Nothing here.</p>
              : shown.map((p) => <PingCard key={p.id} ping={p} onOpen={() => setOpenId(p.id)} />)}
          </div>
        )}
      </aside>

      {composing && <PingModal init={composing} onClose={() => setComposing(null)} />}
    </div>
  )
}
```

- [ ] **Step 4: Run the tests**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/PingPanel.test.tsx`
Expected: 4 passed.

- [ ] **Step 5: Wire the panel into AppShell**

In `frontend/src/components/AppShell.tsx`: import `{ PingPanel } from './PingPanel'`; remove any temporary `{pingsOpen && null}` from Task 7; inside the outer `<div className="flex min-h-screen …">`, after the closing `</div>` of the `flex flex-1 flex-col` column, add:

```tsx
      {pingsOpen && <PingPanel onClose={() => setPingsOpen(false)} />}
```

- [ ] **Step 6: Typecheck, build, and try it**

Run `tsc` and `vite build` (node invocations above), start the backend, sign in. Click the bell: the panel opens on a light surface with Inbox/Sent, search, chips and "Nothing here." Click New Ping, pick the admin user (yourself is fine for a smoke), type a note, Send. The card appears under Sent; the bell badge shows 1 within a few seconds since you also addressed yourself. Ask the user to confirm visually.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PingPanel.tsx frontend/src/components/PingPanel.test.tsx frontend/src/components/AppShell.tsx
git commit -m "feat(pings): slide-over panel behind the bell with inbox/sent, search and filters"
```

---

### Task 11: The Messages page, route and nav entry

**Files:**
- Create: `frontend/src/routes/MessagesPage.tsx`, `frontend/src/routes/MessagesPage.test.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/components/AppShell.tsx`

**Interfaces:**
- Consumes: `listPings` (Task 6); `PingStatusPill` (Task 8); `PingDetail` (Task 8); `PingModal`, `PingInit` (Task 9); `haystack`, `matches`, `FilterChips`, `Box`, `Filter` (Task 10); `BrandCard` with `mark="messages"` (Task 6); `MessagesIcon` (Task 6); `formatActionDate`.
- Produces: default export `MessagesPage` at `/messages`; nav item "Messages".

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/routes/MessagesPage.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PingDetail as PingDetailType, PingSummary } from '../api/pings'
import { formatActionDate } from './formatDate'
import MessagesPage from './MessagesPage'

vi.mock('../api/pings', () => ({
  listPings: vi.fn(), getPing: vi.fn(), replyToPing: vi.fn(), markPingDone: vi.fn(),
  reopenPing: vi.fn(), createPing: vi.fn(), pingDirectory: vi.fn(), pingSuggestions: vi.fn(),
}))
import { listPings, getPing } from '../api/pings'
vi.mock('../auth/useMe', () => ({
  useMe: () => ({ data: { id: 'u2', name: 'Me', email: 'me@x.com', roles: ['APPROVER'],
                          division_id: null, must_change_password: false } }),
}))

const ping: PingSummary = {
  id: 'p1', note: 'GL account on the forklift looks wrong.',
  sender: { id: 'u1', name: 'Dana Whitfield' }, created_at: '2026-09-08T14:22:00+00:00',
  request_id: 'req-1',
  request: { id: 'req-1', number: 'CX000042', status: 'PENDING_L1', division_name: '100 — Ops',
             requestor_name: 'Owner', total_cost: '30000', visible: true },
  recipients: [{ user_id: 'u2', name: 'Me', email: 'me@x.com', read_at: null, completed_at: null }],
  reply_count: 2, unread_replies: 1, unread_for_me: true,
  last_activity_at: '2026-09-08T14:22:00+00:00', completed_at: null, done_by: null, search_blob: '',
}
const readPing: PingSummary = {
  ...ping, id: 'p2', request_id: null, request: null, sender: { id: 'u3', name: 'Ann Reader' },
  unread_for_me: false, note: 'A second, already-read ping.',
}
const detail: PingDetailType = { ...ping, replies: [] }

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}><MemoryRouter><MessagesPage /></MemoryRouter></QueryClientProvider>,
  )
}

describe('MessagesPage', () => {
  it('lists pings in a table with the column headers', async () => {
    vi.mocked(listPings).mockResolvedValue([ping])
    renderPage()
    expect(await screen.findByText('Dana Whitfield')).toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument()
    for (const h of ['From / To', 'Ping', 'Request', 'Replies', 'Status', 'Last activity']) {
      expect(screen.getByText(h)).toBeInTheDocument()
    }
    expect(screen.getByText('CX000042')).toBeInTheDocument()
    expect(screen.getByText('unread')).toBeInTheDocument()
  })

  it('offers Inbox and Sent as tabs, and switching fetches the other box', async () => {
    vi.mocked(listPings).mockResolvedValue([ping])
    renderPage()
    const sent = await screen.findByRole('tab', { name: /sent/i })
    expect(screen.getByRole('tab', { name: /inbox/i })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(sent)
    expect(listPings).toHaveBeenCalledWith('sent')
    expect(sent).toHaveAttribute('aria-selected', 'true')
  })

  it('only bolds the sender cell for an unread ping', async () => {
    vi.mocked(listPings).mockResolvedValue([ping, readPing])
    renderPage()
    const unreadCell = (await screen.findByText('Dana Whitfield')).closest('td')!
    const readCell = screen.getByText('Ann Reader').closest('td')!
    expect(unreadCell.className).toContain('font-semibold')
    expect(readCell.className).not.toContain('font-semibold')
  })

  it('searches by person, note, request number or reply text', async () => {
    vi.mocked(listPings).mockResolvedValue([ping, readPing])
    renderPage()
    await screen.findByText('Dana Whitfield')
    fireEvent.change(screen.getByLabelText('Search messages'), { target: { value: 'cx000042' } })
    expect(screen.getByText('Dana Whitfield')).toBeInTheDocument()
    expect(screen.queryByText('Ann Reader')).toBeNull()
  })

  it('formats last activity through formatActionDate, not the raw ISO string', async () => {
    vi.mocked(listPings).mockResolvedValue([ping])
    renderPage()
    expect(await screen.findByText(formatActionDate(ping.last_activity_at))).toBeInTheDocument()
    expect(screen.queryByText(ping.last_activity_at)).toBeNull()
  })

  it('clicking a row expands the detail inline and clicking again collapses it', async () => {
    vi.mocked(listPings).mockResolvedValue([ping])
    vi.mocked(getPing).mockResolvedValue(detail)
    renderPage()
    const row = (await screen.findByText(/GL account on the forklift/)).closest('tr')!
    fireEvent.click(row)
    expect(await screen.findByText(/GL account on the forklift looks wrong/, { selector: 'p' }))
      .toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(row)
    expect(screen.queryByText(/GL account on the forklift looks wrong/, { selector: 'p' })).toBeNull()
  })

  it('has a New Ping button that opens the modal', async () => {
    vi.mocked(listPings).mockResolvedValue([])
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /new ping/i }))
    expect(screen.getByRole('dialog', { name: /new ping/i })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `node ./node_modules/vitest/vitest.mjs run src/routes/MessagesPage.test.tsx`
Expected: FAIL — cannot resolve `./MessagesPage`.

- [ ] **Step 3: Implement the page**

Create `frontend/src/routes/MessagesPage.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { Fragment, useState } from 'react'

import { listPings, type PingSummary } from '../api/pings'
import { BrandCard } from '../components/ui/BrandCard'
import { Button } from '../components/ui/Button'
import { SendIcon } from '../components/ActionIcons'
import { PingStatusPill } from '../components/PingCard'
import { PingDetail } from '../components/PingDetail'
import { PingModal, type PingInit } from '../components/PingModal'
import { FilterChips, haystack, matches, type Box, type Filter } from '../components/PingPanel'
import { formatActionDate } from './formatDate'

function who(ping: PingSummary, box: Box): string {
  if (box === 'inbox') return ping.sender.name
  const names = ping.recipients.map((r) => r.name)
  return names.length > 2 ? `→ ${names.slice(0, 2).join(', ')} +${names.length - 2}` : `→ ${names.join(', ')}`
}

const TH = 'border-b border-border bg-brand-sky/25 text-left text-xs uppercase tracking-wide text-brand-navy dark:bg-brand-sky/10 dark:text-brand-sky [&>th]:px-3 [&>th]:py-2 [&>th]:font-semibold'

/** The full page is a TABLE in CAPRI's RequestsTable idiom, not the panel's
 *  card list (spec section 8.3). Clicking a row expands the detail INLINE
 *  beneath it; clicking again collapses. */
export default function MessagesPage() {
  const [box, setBox] = useState<Box>('inbox')
  const [filter, setFilter] = useState<Filter>('open')
  const [search, setSearch] = useState('')
  const [openId, setOpenId] = useState<string | null>(null)
  const [composing, setComposing] = useState<PingInit | null>(null)

  const { data: pings = [], isLoading } = useQuery({
    queryKey: ['pings', 'list', box], queryFn: () => listPings(box),
  })

  const term = search.trim().toLowerCase()
  const searched = term ? pings.filter((p) => haystack(p).includes(term)) : pings
  const shown = searched.filter((p) => matches(p, filter))

  const controls = (
    <div className="space-y-3 border-b border-border bg-surface-2 px-7 py-3">
      <div role="tablist" aria-label="Mailbox" className="flex border-b border-border">
        {(['inbox', 'sent'] as Box[]).map((key) => (
          <button key={key} type="button" role="tab" aria-selected={box === key}
            onClick={() => { setBox(key); setOpenId(null) }}
            className={`flex-1 border-b-2 py-2 text-sm font-bold capitalize ${
              box === key ? 'border-accent text-fg' : 'border-transparent text-muted'}`}>
            {key}
          </button>
        ))}
      </div>
      <input value={search} onChange={(e) => setSearch(e.target.value)}
        placeholder="Search person, request or words…" aria-label="Search messages"
        className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg outline-none focus:border-accent" />
      <FilterChips pings={searched} filter={filter} onChange={setFilter} />
    </div>
  )

  return (
    <BrandCard title="Messages" subtitle="Pings between CAPRI users" mark="messages"
      actions={<Button size="sm" onClick={() => setComposing({})}><SendIcon size={14} />New Ping</Button>}
      subheader={controls} bodyClassName="px-0 py-0">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className={TH}>
              <th>From / To</th><th>Ping</th><th>Request</th>
              <th className="text-right">Replies</th><th>Status</th><th>Last activity</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td className="px-3 py-3 text-muted" colSpan={6}>Loading…</td></tr>}
            {!isLoading && shown.length === 0 && (
              <tr><td className="px-3 py-3 text-muted" colSpan={6}>Nothing here.</td></tr>
            )}
            {shown.map((p) => (
              <Fragment key={p.id}>
                <tr onClick={() => setOpenId(openId === p.id ? null : p.id)}
                  className={`cursor-pointer border-b border-border last:border-0 hover:bg-surface-2 ${
                    openId === p.id ? 'ring-1 ring-inset ring-accent' : ''}`}>
                  <td className={`whitespace-nowrap px-3 py-2.5 ${p.unread_for_me ? 'font-semibold' : ''}`}>
                    {p.unread_for_me && <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-accent align-middle" />}
                    {who(p, box)}
                  </td>
                  <td className="max-w-[340px] truncate px-3 py-2.5 text-fg">{p.note}</td>
                  <td className="px-3 py-2.5">
                    {p.request && (
                      <span className="rounded-md border border-border bg-surface-2 px-1.5 py-0.5 text-xs text-muted">
                        {p.request.number}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-muted">{p.reply_count}</td>
                  <td className="px-3 py-2.5"><PingStatusPill ping={p} /></td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-muted">{formatActionDate(p.last_activity_at)}</td>
                </tr>
                {openId === p.id && (
                  <tr className="border-b border-border bg-surface-2/60">
                    <td colSpan={6} className="p-0">
                      <div className="max-w-[720px]"><PingDetail id={p.id} onBack={() => setOpenId(null)} /></div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {composing && <PingModal init={composing} onClose={() => setComposing(null)} />}
    </BrandCard>
  )
}
```

- [ ] **Step 4: Route and nav**

In `frontend/src/App.tsx`: `import MessagesPage from './routes/MessagesPage'` and add `<Route path="/messages" element={<MessagesPage />} />` directly after the `/reports` route.

In `frontend/src/components/AppShell.tsx`: add `MessagesIcon` to the `./NavIcons` import and insert into the Overview section, after My Requests:

```tsx
      { to: '/messages', label: 'Messages', icon: MessagesIcon, roles: [] },
```

- [ ] **Step 5: Run the tests, typecheck, build**

Run: `node ./node_modules/vitest/vitest.mjs run src/routes/MessagesPage.test.tsx` — expected 7 passed. Then `tsc` and `vite build`. Start the backend and open `/messages`: sky-tinted header row, Inbox/Sent tabs, the ping from Task 10 listed; click it, the detail expands beneath the row. Ask the user to confirm visually.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/MessagesPage.tsx frontend/src/routes/MessagesPage.test.tsx frontend/src/App.tsx frontend/src/components/AppShell.tsx
git commit -m "feat(pings): Messages page at /messages with inline detail, plus sidebar entry"
```

---

### Task 12: Entry points on the request detail page and table rows

**Files:**
- Modify: `frontend/src/routes/RequestDetailPage.tsx` (imports; the "Download PDF" section around line 100)
- Modify: `frontend/src/routes/RequestsListPage.tsx` (`RequestsTable`, lines ~113-180)
- Test: `frontend/src/routes/RequestDetailPage.test.tsx`, `frontend/src/routes/RequestsListPage.test.tsx` (append)

**Interfaces:**
- Consumes: `PingModal`, `PingInit` (Task 9); `Button` `size="sm"` (Task 6); `SendIcon` (Task 6).

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/routes/RequestDetailPage.test.tsx` (inside the existing `describe`, using its `renderPage` and `makeRequest` helpers; the file already mocks `../api/requests` and `../auth/useMe`). Also add at the top, next to the other mocks:

```tsx
vi.mock('../api/pings', () => ({
  createPing: vi.fn(), pingDirectory: vi.fn(() => Promise.resolve([])),
  pingSuggestions: vi.fn(() => Promise.resolve([])),
}))
```

and the test:

```tsx
  it('offers a small filled Ping button that opens the modal with the request attached', async () => {
    vi.mocked(getRequest).mockResolvedValue(makeRequest())
    renderPage()
    const ping = await screen.findByRole('button', { name: /^ping$/i })
    expect(ping.className).toContain('bg-accent')
    expect(ping.className).toContain('text-xs')
    fireEvent.click(ping)
    expect(screen.getByRole('dialog', { name: /new ping/i })).toBeInTheDocument()
    expect(screen.getByText('CX000042')).toBeInTheDocument()
  })
```

Append to `frontend/src/routes/RequestsListPage.test.tsx` (inside its `describe`, using `renderPage` and `mockMe`; add the same `vi.mock('../api/pings', …)` block next to the existing mocks):

```tsx
  it('each row has an accent Ping icon that opens the modal for that request', async () => {
    mockMe(['REQUESTOR'])
    vi.mocked(reqApi.listRequests).mockResolvedValue([{
      id: 'req-1', number: 'CX000042', status: 'DRAFT', total_cost: '100',
      division_name: '100 — Ops', requestor_name: 'Owner', assignee_name: null, created_at: null,
    }])
    renderPage()
    const ping = await screen.findByRole('button', { name: 'Ping about CX000042' })
    expect(ping.className).toContain('text-accent')
    fireEvent.click(ping)
    expect(screen.getByRole('dialog', { name: /new ping/i })).toBeInTheDocument()
    expect(screen.getAllByText('CX000042').length).toBeGreaterThan(1)   // row + modal chip
  })
```

- [ ] **Step 2: Run to verify they fail**

Run: `node ./node_modules/vitest/vitest.mjs run src/routes/RequestDetailPage.test.tsx src/routes/RequestsListPage.test.tsx`
Expected: the two new tests FAIL (no Ping button); all existing tests still pass.

- [ ] **Step 3: Detail page button**

In `frontend/src/routes/RequestDetailPage.tsx`:
- Add imports: `import { PingModal, type PingInit } from '../components/PingModal'` and add `SendIcon` to the `ActionIcons` import.
- Add state next to the others: `const [pinging, setPinging] = useState<PingInit | null>(null)`.
- In the `<section className="flex flex-wrap items-center gap-4 border-y border-border py-2.5">` block, directly after the Download PDF `<a>`, add:

```tsx
        <Button size="sm" disabled={busy}
          onClick={() => setPinging({ request: { id: req.id, number: req.number } })}>
          <SendIcon size={14} />Ping
        </Button>
```

- Before the closing tag of the outer `<div className="max-w-3xl space-y-4">`, add:

```tsx
      {pinging && <PingModal init={pinging} onClose={() => setPinging(null)} />}
```

- [ ] **Step 4: Row icon on RequestsTable**

In `frontend/src/routes/RequestsListPage.tsx`:
- Add imports: `import { PingModal, type PingInit } from '../components/PingModal'`; add `SendIcon` to the `ActionIcons` import.
- In `RequestsTable`, add `const [pinging, setPinging] = useState<PingInit | null>(null)` next to the `sort` state (before the early `return` for empty rows — hooks must run unconditionally, so move the `if (rows.length === 0)` return below both `useState` calls).
- In the last `<td className="py-2.5 pr-2 text-right">`, wrap the existing View link and a new button in a flex container:

```tsx
              <td className="py-2.5 pr-2 text-right">
                <span className="inline-flex items-center gap-2">
                  <button
                    type="button"
                    aria-label={`Ping about ${r.number}`}
                    title="Ping"
                    onClick={() => setPinging({ request: { id: r.id, number: r.number } })}
                    className="inline-flex text-accent hover:opacity-80"
                  >
                    <SendIcon size={18} />
                  </button>
                  <Link
                    to={`/requests/${r.id}`}
                    aria-label={`View ${r.number}`}
                    title="View"
                    className="inline-flex text-muted hover:text-accent"
                  >
                    <ViewIcon size={18} />
                  </Link>
                </span>
              </td>
```

- After the closing `</table>` inside the `overflow-x-auto` div, add `{pinging && <PingModal init={pinging} onClose={() => setPinging(null)} />}`.

The Dashboard's approvals table renders this same component, so it gets the icon with no further change.

- [ ] **Step 5: Run the tests, typecheck, build**

Run: `node ./node_modules/vitest/vitest.mjs run` — expected: all pass, including the two new ones. Then `tsc` and `vite build`. In the browser: the request detail page shows a small blue Ping button beside Download PDF; the Requests list and Dashboard rows show a blue paper plane beside the eye. Ask the user to confirm visually.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/RequestDetailPage.tsx frontend/src/routes/RequestDetailPage.test.tsx frontend/src/routes/RequestsListPage.tsx frontend/src/routes/RequestsListPage.test.tsx
git commit -m "feat(pings): Ping entry points on the request detail page and table rows"
```

---

### Task 13: Full gates, end-to-end check, docs

**Files:**
- Modify: `CLAUDE.md` (Backend layout, Data model, Frontend layout; new "Pings" section after "Comment thread")

- [ ] **Step 1: Backend gate**

Run from `backend/`: `pytest -q`
Expected: all pass (271 + 36 new). Fix anything red before moving on.

- [ ] **Step 2: Frontend gates**

Run from `frontend/`: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `node ./node_modules/vitest/vitest.mjs run`, `node ./node_modules/vite/bin/vite.js build`.
Expected: clean, all pass, build succeeds.

- [ ] **Step 3: End-to-end walk with two users**

Start the backend. In Admin → Users create a second active user (any role) if none exists. In one browser sign in as admin, open a request, click Ping, pick the second user (they appear under Suggested if they are the requestor or an eligible approver), send. In a private window sign in as the second user: the bell shows 1; open the panel, open the ping, the request chip links (or not, if they cannot view it), reply, Mark done. Back as admin: the conversation is now in the admin's Inbox (answered), shows "Done by <name>", and the Messages page lists it under Done. Ask the user to confirm each visible step.

- [ ] **Step 4: Document in CLAUDE.md**

Add to `CLAUDE.md`:
- Backend layout: `pings` (`/api/pings`, every signed-in user; see Pings) in the blueprints list; `ping_service` in the services list.
- Data model: `**Ping** / **PingRecipient**` bullet pointing at the Pings section.
- Frontend layout: `MessagesPage` (`/messages`) in routes; `PingBell`/`PingPanel`/`PingCard`/`PingDetail`/`PingModal` in components; `Button` `size` prop in `components/ui/`.
- A new section after "Comment thread":

```markdown
## Pings (in-app messaging)

Spec: `docs/superpowers/specs/2026-09-09-in-app-messaging-design.md`. Ported from
SCORE's shipped Pings; built 2026-09-09.

- **Naming is split on purpose:** the sidebar/page say **Messages** (`/messages`,
  `MessagesPage`); every button and all code say **ping** (`pings`,
  `ping_recipients`, `ping_service`, `/api/pings`, `Ping*` components).
- **A reply is a child row** (`pings.parent_id` → the root, never another reply).
  Read is **personal** (`ping_recipients.read_at`); done is **shared** — first tick
  closes it for the roster, derived at read time by `apply_shared_done`, never stored.
- **Unscoped by design:** anyone can ping anyone (`directory()` is every active
  user). A ping may reference a request the recipient cannot open: the summary
  renders, the deep link only when `request_service.can_view` says so.
- **Not the comment thread.** Comments belong to the request, print in the PDF and
  email the other side. Pings belong to people, carry read/done state, never print,
  never email (deliberately deferred), never change workflow state.
- Ordering is `(last_activity_at, last_activity_id)` — ids are uuid4, so the id is
  only a tiebreaker.
- `delete_draft` returns **409** for a draft that has pings (explicit check; SQLite
  FKs are not enforced here).
- Ping buttons are `Button variant="primary" size="sm"` with `SendIcon`; table rows
  use an icon-only `text-accent` paper plane beside View.
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md for Pings (in-app messaging)"
```

---

## Self-Review

**Spec coverage.** §1 naming → Global Constraints, Tasks 6/11. §2 tables, UUIDs, NO ACTION, migration → Task 1; explicit delete guard → Task 5. §3 read personal / done shared / answered-in-both / ordering → Tasks 2–4 with tests for each. §4 live request summary, never a nudge → Task 2 `_request_summary`, no `notify` import anywhere. §5 unscoped directory + `visible` gating the link → Tasks 2, 4, 8 (chip vs link test). §6 comment thread stays untouched → no task modifies `CommentThread`/`comment_service`; documented in Task 13. §7 service/blueprint/schema → Tasks 2–5, route order noted. §8.1 files → Tasks 6–11. §8.2 bell → Task 7. §8.3 table idiom, Inbox/Sent tabs, inline expand → Task 11. §8.4 panel → Task 10. §8.5 modal, suggested first → Task 9. §8.6 Button size + filled sm + row icon → Tasks 6, 9, 10, 11, 12. §8.7 entry points → Task 12 (detail page, RequestsTable which the Dashboard shares, panel + page New Ping). §9 out of scope → nothing planned. §10 errors → Tasks 2–5 tests. §11 testing → every task; gates in Task 13. §12 open question → untouched.

**Placeholder scan.** No TBD/TODO; every code step has code; Task 4 Step 4 carries a concrete remediation instead of "handle it".

**Type consistency.** `RequestRef` (Task 6) matches `_request_summary` keys (Task 2): `id, number, status, division_name, requestor_name, total_cost, visible`. `PingSummary.request_id` / `.request` match `_summarize`. `DirectoryUser.division_name` matches `_user_out`. `PingInit.request` is `{id, number}` in Task 9 and used that way in Tasks 10–12. `FilterChips`, `haystack`, `matches`, `Box`, `Filter` are exported from `PingPanel.tsx` (Task 10) and imported by `MessagesPage.tsx` (Task 11). Query keys are `['pings', 'unread']`, `['pings', 'list', box]`, `['pings', 'detail', id]`, `['pings', 'directory']`, `['pings', 'suggestions', requestId]`; every mutation invalidates `['pings']`.
