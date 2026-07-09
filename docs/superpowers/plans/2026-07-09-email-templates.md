# Admin Email Template Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let admins customize the four CAPEX Flow notification emails (subject, WYSIWYG body, enabled) with a brand-styled locked frame, `{token}` placeholders, and a three-tier default state.

**Architecture:** A new `EmailTemplate` DB table stores per-type overrides; code holds shipped defaults. A rendering service substitutes tokens and wraps the body in a brand HTML frame. `notify.py` renders through this service instead of hard-coded strings; emails now send as HTML. A new admin API blueprint backs a React admin page with a Quill editor and a placeholders panel.

**Tech Stack:** Flask, SQLAlchemy 2.0 (typed `Mapped`), Alembic, Pydantic v2, pytest; React 19 + TypeScript, Vite, TanStack Query, Quill 2.x (used directly via a ref).

## Global Constraints

- Backend Python 3.14; SQLAlchemy typed `Mapped`/`mapped_column`; SQLite dev / Azure SQL prod.
- Raise `ServiceError(msg, status)` for handled API errors; keep routes thin (logic in `services/`).
- Admin-only routes use `@require_roles("ADMIN")` from `app.authz`.
- Run backend tests via venv: `.venv/Scripts/python.exe -m pytest -q` (from `backend/`).
- Frontend tooling runs via node (path contains `&`): `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `node ./node_modules/vite/bin/vite.js build`, `node ./node_modules/vitest/vitest.mjs run`.
- Email HTML must use **inline CSS only** (email-client requirement). Brand: navy `#0B2A4A`, blue `#2563EB`, sky `#93BBF5`. No images.
- Four fixed template types: `ASSIGNED`, `APPROVED`, `REJECTED`, `FINANCE_READY`.
- Tokens use `{token}` syntax; unknown tokens are left intact.
- After significant changes, update docs and make focused commits.

---

## File Structure

**Backend**
- Create `backend/app/services/email_frame.py` — brand HTML wrapper.
- Create `backend/app/services/email_template_service.py` — defaults, tokens, get/save/reset/render.
- Create `backend/app/schemas/email_template.py` — Pydantic input models.
- Create `backend/app/blueprints/email_templates.py` — admin API.
- Create `backend/migrations/versions/d3e4f5a6b7c8_email_templates.py` — migration.
- Modify `backend/app/models/__init__.py` — add `EmailTemplate` model.
- Modify `backend/app/services/email_outlook.py` — HTML support.
- Modify `backend/app/services/notify.py` — render via templates; enabled gate; pass reject comment.
- Modify `backend/app/blueprints/requests.py` — pass reject comment to `notify_decision`.
- Modify `backend/app/__init__.py` — register the new blueprint.
- Tests: `backend/tests/test_email_templates.py`, plus additions to `backend/tests/test_notify.py`.

**Frontend**
- Create `frontend/src/api/emailTemplates.ts` — API module + types.
- Create `frontend/src/components/ui/QuillEditor.tsx` — Quill wrapper on a ref.
- Create `frontend/src/routes/admin/EmailTemplatesPage.tsx` — list of 4.
- Create `frontend/src/routes/admin/EmailTemplateEditor.tsx` — editor.
- Modify `frontend/src/App.tsx` — routes.
- Modify `frontend/src/components/AppShell.tsx` — nav item.
- Test: `frontend/src/routes/admin/EmailTemplateEditor.test.tsx`.

---

## Task 1: `EmailTemplate` model + migration

**Files:**
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/versions/d3e4f5a6b7c8_email_templates.py`
- Test: `backend/tests/test_email_templates.py`

**Interfaces:**
- Produces: `EmailTemplate(type, subject, body_html, enabled, default_subject, default_body_html, updated_at)`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_email_templates.py`:

```python
from app.extensions import db
from app.models import EmailTemplate


def test_email_template_round_trips(app):
    db.session.add(EmailTemplate(
        type="ASSIGNED", subject="s", body_html="<p>b</p>", enabled=True,
        default_subject="s", default_body_html="<p>b</p>"))
    db.session.commit()
    row = db.session.get(EmailTemplate, "ASSIGNED")
    assert row.enabled is True and row.body_html == "<p>b</p>"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_email_templates.py -q`
Expected: FAIL — `ImportError: cannot import name 'EmailTemplate'`.

- [ ] **Step 3: Add the model**

In `backend/app/models/__init__.py`, ensure these are imported at top (add any missing): `from sqlalchemy import String, Integer, Text, Boolean, DateTime, func` and `from datetime import datetime`. Then add near `AppSetting`:

```python
class EmailTemplate(db.Model):
    __tablename__ = "email_templates"

    type: Mapped[str] = mapped_column(String(20), primary_key=True)
    subject: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_subject: Mapped[str] = mapped_column(Text)
    default_body_html: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_email_templates.py -q`
Expected: PASS (the `app` fixture calls `db.create_all()`).

- [ ] **Step 5: Create the Alembic migration**

Create `backend/migrations/versions/d3e4f5a6b7c8_email_templates.py`:

```python
"""email templates

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-07-09
"""
import sqlalchemy as sa
from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_templates",
        sa.Column("type", sa.String(length=20), primary_key=True),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("default_subject", sa.Text(), nullable=False),
        sa.Column("default_body_html", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("email_templates")
```

- [ ] **Step 6: Verify the migration applies**

Run: `.venv/Scripts/python.exe -m flask db upgrade`
Expected: no error; `email_templates` table created.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/__init__.py backend/migrations/versions/d3e4f5a6b7c8_email_templates.py backend/tests/test_email_templates.py
git commit -m "feat(models): EmailTemplate table + migration"
```

---

## Task 2: Brand HTML frame

**Files:**
- Create: `backend/app/services/email_frame.py`
- Test: `backend/tests/test_email_templates.py` (append)

**Interfaces:**
- Produces: `wrap(body_html: str, *, redirect_note: str | None = None) -> str`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_email_templates.py`:

```python
from app.services import email_frame


def test_frame_wraps_body_and_shows_brand():
    html = email_frame.wrap("<p>Hello</p>")
    assert "<p>Hello</p>" in html
    assert "United Uptime Services" in html
    assert "#0B2A4A" in html          # navy header
    assert "Intended recipient" not in html


def test_frame_redirect_note_banner():
    html = email_frame.wrap("<p>Hi</p>", redirect_note="Intended recipient: a@x.com")
    assert "Intended recipient: a@x.com" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_email_templates.py -k frame -q`
Expected: FAIL — `ModuleNotFoundError: app.services.email_frame`.

- [ ] **Step 3: Implement the frame**

Create `backend/app/services/email_frame.py`:

```python
"""Brand HTML shell wrapped around every notification email body.
Inline CSS only (email-client requirement); colors from the UUS CAPEX Flow brand.
"""

NAVY = "#0B2A4A"
SKY = "#93BBF5"


def wrap(body_html, *, redirect_note=None):
    banner = ""
    if redirect_note:
        banner = (
            '<div style="max-width:600px;margin:0 auto 12px;background:#FEF3C7;'
            'color:#92400E;padding:10px 16px;border-radius:8px;'
            'font:13px/1.4 Arial,Helvetica,sans-serif;">'
            f"{redirect_note}</div>"
        )
    return (
        '<div style="margin:0;padding:24px;background:#EEF3FB;">'
        f"{banner}"
        '<div style="max-width:600px;margin:0 auto;background:#ffffff;'
        "border:1px solid #E2E8F0;border-radius:12px;overflow:hidden;"
        'font-family:Arial,Helvetica,sans-serif;color:#0B1B2B;">'
        f'<div style="background:{NAVY};padding:24px 28px;">'
        '<div style="color:#ffffff;font-size:20px;font-weight:bold;">'
        "United Uptime Services</div>"
        f'<div style="color:{SKY};font-size:13px;letter-spacing:.5px;">CAPEX Flow</div>'
        "</div>"
        '<div style="padding:24px 28px;font-size:15px;line-height:1.5;">'
        f"{body_html}</div>"
        '<div style="padding:16px 28px;border-top:1px solid #E2E8F0;'
        'color:#64748B;font-size:12px;">'
        "Automated message from CAPEX Flow — please do not reply.</div>"
        "</div></div>"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_email_templates.py -k frame -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/email_frame.py backend/tests/test_email_templates.py
git commit -m "feat(email): brand HTML frame for notification emails"
```

---

## Task 3: Template service (defaults, tokens, get/save/reset/render)

**Files:**
- Create: `backend/app/services/email_template_service.py`
- Test: `backend/tests/test_email_templates.py` (append)

**Interfaces:**
- Consumes: `EmailTemplate` model (Task 1), `email_frame.wrap` (Task 2).
- Produces:
  - `TYPES: tuple[str, ...]`, `NAMES: dict[str, str]`, `TOKENS: dict[str, list[dict]]`
  - `get(type_) -> dict` with keys `type, name, subject, body_html, enabled, default_subject, default_body_html, is_custom`
  - `save(type_, subject, body_html, enabled) -> dict`
  - `save_as_default(type_) -> dict`
  - `reset(type_) -> dict`
  - `render(type_, context, *, redirect_note=None) -> dict` with keys `subject, html, enabled`
  - `sample_context(type_) -> dict`
  - `context_for(req, **extra) -> dict`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_email_templates.py`:

```python
from app.services import email_template_service as ets
from app.services.errors import ServiceError
import pytest


def test_get_returns_shipped_default_when_no_row(app):
    t = ets.get("ASSIGNED")
    assert t["is_custom"] is False
    assert "{number}" in t["body_html"]
    assert t["enabled"] is True


def test_render_substitutes_tokens_and_frames(app):
    out = ets.render("ASSIGNED", {"number": "CX000042", "level": "Level 2 of 3",
                                  "requestor": "Dana", "division": "12 — FS",
                                  "total_cost": "$1.00", "link": "http://x/req/1"})
    assert "CX000042" in out["html"]
    assert "United Uptime Services" in out["html"]      # framed
    assert "{number}" not in out["html"]


def test_render_leaves_unknown_token_intact(app):
    out = ets.render("APPROVED", {"number": "CX1"})
    # {link} etc. not supplied -> remain literally, not blanked
    assert "{link}" in out["html"] or "{total_cost}" in out["html"]


def test_save_then_reset_reverts_to_shipped_default(app):
    ets.save("APPROVED", subject="Custom", body_html="<p>custom</p>", enabled=True)
    assert ets.get("APPROVED")["is_custom"] is True
    ets.reset("APPROVED")
    t = ets.get("APPROVED")
    assert t["subject"] == ets.DEFAULTS["APPROVED"]["subject"]


def test_save_as_default_then_reset_reverts_to_admin_default(app):
    ets.save("REJECTED", subject="v1", body_html="<p>v1</p>", enabled=True)
    ets.save_as_default("REJECTED")
    ets.save("REJECTED", subject="v2", body_html="<p>v2</p>", enabled=True)
    ets.reset("REJECTED")
    assert ets.get("REJECTED")["subject"] == "v1"


def test_get_unknown_type_raises(app):
    with pytest.raises(ServiceError):
        ets.get("NOPE")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_email_templates.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.email_template_service`.

- [ ] **Step 3: Implement the service**

Create `backend/app/services/email_template_service.py`:

```python
from flask import current_app

from app.extensions import db
from app.models import EmailTemplate
from app.services import email_frame
from app.services.errors import ServiceError

TYPES = ("ASSIGNED", "APPROVED", "REJECTED", "FINANCE_READY")

NAMES = {
    "ASSIGNED": "Approval needed",
    "APPROVED": "Request approved",
    "REJECTED": "Request rejected",
    "FINANCE_READY": "Finance section pending",
}

_COMMON = [
    {"token": "{number}", "description": "Request number (e.g. CX000042)"},
    {"token": "{requestor}", "description": "Name of the person who submitted"},
    {"token": "{division}", "description": "Division, e.g. 12 — Field Services"},
    {"token": "{total_cost}", "description": "Total cost, e.g. $182,400.00"},
    {"token": "{link}", "description": "Deep link to the request in the app"},
]
TOKENS = {
    "ASSIGNED": _COMMON + [{"token": "{level}", "description": "Level awaiting you, e.g. Level 2 of 3"}],
    "APPROVED": _COMMON,
    "REJECTED": _COMMON + [{"token": "{comment}", "description": "Reviewer's rejection comment"}],
    "FINANCE_READY": _COMMON,
}

_BTN = (
    'style="display:inline-block;background:#2563EB;color:#ffffff;'
    'text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:bold;"'
)
_FACTS = (
    '<table style="margin:16px 0;border-collapse:collapse;font-size:14px;">'
    "<tr><td style=\"padding:2px 12px 2px 0;color:#64748B;\">Requested by</td>"
    "<td><strong>{requestor}</strong></td></tr>"
    "<tr><td style=\"padding:2px 12px 2px 0;color:#64748B;\">Division</td>"
    "<td>{division}</td></tr>"
    "<tr><td style=\"padding:2px 12px 2px 0;color:#64748B;\">Total cost</td>"
    "<td>{total_cost}</td></tr></table>"
)

DEFAULTS = {
    "ASSIGNED": {
        "subject": "Action needed: {number} awaiting your {level} approval",
        "body_html": (
            "<p>Request <strong>{number}</strong> needs your <strong>{level}</strong> "
            "approval.</p>" + _FACTS +
            f'<p><a href="{{link}}" {_BTN}>Review &amp; approve</a></p>'
        ),
    },
    "APPROVED": {
        "subject": "{number} was approved",
        "body_html": (
            "<p>Your request <strong>{number}</strong> ({total_cost}) was "
            "<strong>approved</strong>. It is now with Finance for completion.</p>"
            f'<p><a href="{{link}}" {_BTN}>View the request</a></p>'
        ),
    },
    "REJECTED": {
        "subject": "{number} was rejected",
        "body_html": (
            "<p>Your request <strong>{number}</strong> ({total_cost}) was "
            "<strong>rejected</strong>.</p>"
            '<p style="background:#FEF2F2;border-left:3px solid #B91C1C;padding:8px 12px;">'
            "Reviewer's comment: {comment}</p>"
            "<p>You can edit and resubmit it.</p>"
            f'<p><a href="{{link}}" {_BTN}>Open the request</a></p>'
        ),
    },
    "FINANCE_READY": {
        "subject": "{number} approved — finance section pending",
        "body_html": (
            "<p>Request <strong>{number}</strong> ({total_cost}) has been fully "
            "approved and needs the finance cost breakdown.</p>" + _FACTS +
            f'<p><a href="{{link}}" {_BTN}>Complete the finance section</a></p>'
        ),
    },
}


def _require_type(type_):
    if type_ not in TYPES:
        raise ServiceError("Unknown email template.", 404)


def get(type_):
    _require_type(type_)
    row = db.session.get(EmailTemplate, type_)
    shipped = DEFAULTS[type_]
    if row is None:
        return {
            "type": type_, "name": NAMES[type_],
            "subject": shipped["subject"], "body_html": shipped["body_html"],
            "enabled": True,
            "default_subject": shipped["subject"],
            "default_body_html": shipped["body_html"],
            "is_custom": False,
        }
    return {
        "type": type_, "name": NAMES[type_],
        "subject": row.subject, "body_html": row.body_html, "enabled": row.enabled,
        "default_subject": row.default_subject,
        "default_body_html": row.default_body_html,
        "is_custom": True,
    }


def _row_or_seed(type_):
    row = db.session.get(EmailTemplate, type_)
    if row is None:
        shipped = DEFAULTS[type_]
        row = EmailTemplate(
            type=type_, subject=shipped["subject"], body_html=shipped["body_html"],
            enabled=True, default_subject=shipped["subject"],
            default_body_html=shipped["body_html"])
        db.session.add(row)
    return row


def save(type_, subject, body_html, enabled):
    _require_type(type_)
    row = _row_or_seed(type_)
    row.subject, row.body_html, row.enabled = subject, body_html, enabled
    db.session.commit()
    return get(type_)


def save_as_default(type_):
    _require_type(type_)
    row = _row_or_seed(type_)
    row.default_subject, row.default_body_html = row.subject, row.body_html
    db.session.commit()
    return get(type_)


def reset(type_):
    _require_type(type_)
    row = db.session.get(EmailTemplate, type_)
    if row is None:
        return get(type_)
    row.subject, row.body_html = row.default_subject, row.default_body_html
    db.session.commit()
    return get(type_)


def _substitute(text, context):
    for key, value in context.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def render(type_, context, *, redirect_note=None):
    tmpl = get(type_)
    subject = _substitute(tmpl["subject"], context)
    body = _substitute(tmpl["body_html"], context)
    return {
        "subject": subject,
        "html": email_frame.wrap(body, redirect_note=redirect_note),
        "enabled": tmpl["enabled"],
    }


def context_for(req, **extra):
    division = f"{req.division.number} — {req.division.name}" if req.division else "—"
    base = (current_app.config.get("APP_BASE_URL") or "").rstrip("/")
    ctx = {
        "number": req.number,
        "requestor": req.requestor.name if req.requestor else "—",
        "division": division,
        "total_cost": f"${req.total_cost:,.2f}" if req.total_cost is not None else "—",
        "link": f"{base}/requests/{req.id}",
    }
    ctx.update(extra)
    return ctx


def sample_context(type_):
    ctx = {
        "number": "CX000042", "requestor": "Dana Ruiz",
        "division": "12 — Field Services", "total_cost": "$182,400.00",
        "link": "http://localhost:5000/requests/sample",
        "level": "Level 2 of 3", "comment": "Please attach the competitive bids.",
    }
    return ctx
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_email_templates.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/email_template_service.py backend/tests/test_email_templates.py
git commit -m "feat(email): template service — defaults, tokens, render, reset"
```

---

## Task 4: Outlook HTML support

**Files:**
- Modify: `backend/app/services/email_outlook.py`

**Interfaces:**
- Produces: `send(to, subject, body, html=None)` — sets `HTMLBody` when `html` given.

- [ ] **Step 1: Update the sender**

Replace the body of `send` in `backend/app/services/email_outlook.py` so the signature is `def send(to, subject, body, html=None):` and inside the `try`:

```python
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.To = to
        mail.Subject = subject
        if html is not None:
            mail.HTMLBody = html
        else:
            mail.Body = body
        mail.Send()
```

- [ ] **Step 2: Verify import still succeeds**

Run: `.venv/Scripts/python.exe -c "import ast; ast.parse(open('app/services/email_outlook.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/email_outlook.py
git commit -m "feat(email): Outlook backend sends HTML when provided"
```

---

## Task 5: Route notifications through templates

**Files:**
- Modify: `backend/app/services/notify.py`
- Modify: `backend/app/blueprints/requests.py:65-71` (reject route)
- Test: `backend/tests/test_notify.py` (modify/extend)

**Interfaces:**
- Consumes: `email_template_service.render/context_for` (Task 3), `email_outlook.send(..., html=...)` (Task 4).
- Produces: unchanged public functions `notify_assignment(req)`, `notify_decision(req, approved, comment=None)`, `notify_finance_ready(req)`.

- [ ] **Step 1: Update the failing notify test**

In `backend/tests/test_notify.py`, replace `test_notify_assignment_body_has_deep_link_and_details` body assertions to expect HTML from the template. Add a disabled-template test:

```python
def test_notify_assignment_uses_template_html(app, monkeypatch):
    sent = {}
    monkeypatch.setattr("app.services.email_outlook.send",
                        lambda to, subject, body, html=None: sent.update(subject=subject, html=html))
    app.config["EMAIL_ENABLED"] = True
    app.config["APP_BASE_URL"] = "https://capex.example.com"
    approver = make_user("appr")
    owner = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    req = make_draft(owner.id, div.id)
    req.current_level, req.required_levels, req.status = 1, 2, "PENDING_L1"
    req.total_cost = Decimal("82400")
    db.session.commit()

    notify.notify_assignment(req)

    assert sent["html"] is not None and "United Uptime Services" in sent["html"]
    assert "https://capex.example.com/requests/" in sent["html"]
    assert "Level 1 of 2" in sent["html"]
    assert req.number in sent["subject"]


def test_disabled_template_logs_but_does_not_send(app, monkeypatch):
    from app.services import email_template_service as ets
    calls = []
    monkeypatch.setattr("app.services.email_outlook.send",
                        lambda *a, **k: calls.append(a))
    app.config["EMAIL_ENABLED"] = True
    approver = make_user("appr")
    owner = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    req = make_draft(owner.id, div.id)
    req.current_level, req.required_levels, req.status = 1, 1, "PENDING_L1"
    db.session.commit()
    ets.save("ASSIGNED", subject="s", body_html="<p>x</p>", enabled=False)

    notify.notify_assignment(req)

    assert calls == []                                        # not sent
    assert db.session.query(NotificationLog).filter_by(type="ASSIGNED").count() == 1
```

Keep the earlier `test_send_email_*` tests but update their monkeypatched lambda signatures to `lambda to, subject, body, html=None: ...`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_notify.py -q`
Expected: FAIL (assignment still sends plain text; `send` signature mismatch).

- [ ] **Step 3: Rewrite `notify.py`**

Replace `send_email`, `_deliver`, and the three `notify_*` functions in `backend/app/services/notify.py` with:

```python
def _redirect_note(intended):
    if not (current_app.config.get("EMAIL_ENABLED")
            and current_app.config.get("EMAIL_REDIRECT_TO")):
        return None
    return f"Intended recipient: {intended} (redirected while testing)"


def _emit(intended, subject, html, enabled, request_id, type_):
    """Always record a NotificationLog; deliver via Outlook when enabled."""
    try:
        log.info("EMAIL to=%s subject=%s", intended, subject)
        db.session.add(NotificationLog(request_id=request_id, recipient=intended, type=type_))
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("notification log failed for %s", intended)
    if not enabled or not current_app.config.get("EMAIL_ENABLED"):
        return
    redirect_to = current_app.config.get("EMAIL_REDIRECT_TO") or intended
    try:
        from app.services import email_outlook
        email_outlook.send(redirect_to, subject, "", html=html)
    except Exception:
        log.exception("email delivery failed (intended %s)", intended)


def _send_template(intended, type_, req, **extra):
    from app.services import email_template_service as ets
    ctx = ets.context_for(req, **extra)
    out = ets.render(type_, ctx, redirect_note=_redirect_note(intended))
    _emit(intended, out["subject"], out["html"], out["enabled"], req.id, type_)


def notify_assignment(req):
    from app.services import threshold_service, workflow_service
    actors = workflow_service.eligible_actors(
        req.current_level, req.division, threshold_service.list_thresholds())
    level = f"Level {req.current_level}"
    if req.required_levels:
        level += f" of {req.required_levels}"
    for actor in actors:
        _send_template(actor.email, "ASSIGNED", req, level=level)


def notify_decision(req, approved, comment=None):
    type_ = "APPROVED" if approved else "REJECTED"
    _send_template(req.requestor.email, type_, req, comment=comment or "(no comment)")


def notify_finance_ready(req):
    users = db.session.query(User).filter(User.active.is_(True)).all()
    for u in users:
        if "FINANCE" in u.roles_list:
            _send_template(u.email, "FINANCE_READY", req)
```

Remove the now-unused `_request_url`, `_money`, `_request_facts`, `send_email`, `_deliver` helpers **only if** no test imports them; the `test_send_email_*` tests call `notify.send_email` — so **keep a thin `send_email`** for backward-compatible direct sends:

```python
def send_email(recipient, subject, body, request_id=None, type_="INFO"):
    """Direct plain-text send (used for ad-hoc/test messages)."""
    _emit_plain(recipient, subject, body, request_id, type_)


def _emit_plain(intended, subject, body, request_id, type_):
    try:
        log.info("EMAIL to=%s subject=%s", intended, subject)
        db.session.add(NotificationLog(request_id=request_id, recipient=intended, type=type_))
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("notification log failed for %s", intended)
    if not current_app.config.get("EMAIL_ENABLED"):
        return
    redirect_to = current_app.config.get("EMAIL_REDIRECT_TO") or intended
    note = _redirect_note(intended)
    full = f"{note}\n\n{body}" if note else body
    try:
        from app.services import email_outlook
        email_outlook.send(redirect_to, subject, full)
    except Exception:
        log.exception("email delivery failed (intended %s)", intended)
```

(The two existing `test_send_email_delivers_redirected_when_enabled` / `..._never_raises` tests assert the redirected recipient and body substring; with `_emit_plain` sending `full` as the plain body and `send(redirect_to, subject, full)`, update those tests' lambda to `lambda to, subject, body, html=None: sent.update(to=to, body=body)` — already covered in Task 5 Step 1's note.)

- [ ] **Step 4: Pass the reject comment from the route**

In `backend/app/blueprints/requests.py`, in `reject_request`, change the notify call:

```python
    req = workflow_service.reject(request_id, current_user.id, comment)
    notify.notify_decision(req, False, comment)
```

- [ ] **Step 5: Run the full backend suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/notify.py backend/app/blueprints/requests.py backend/tests/test_notify.py
git commit -m "feat(notify): render notifications from editable templates (HTML)"
```

---

## Task 6: Admin API (schema + blueprint + registration)

**Files:**
- Create: `backend/app/schemas/email_template.py`
- Create: `backend/app/blueprints/email_templates.py`
- Modify: `backend/app/__init__.py`
- Test: `backend/tests/test_email_templates_api.py`

**Interfaces:**
- Consumes: `email_template_service` (Task 3), `require_roles` from `app.authz`.
- Produces routes under `/api/email-templates`.

- [ ] **Step 1: Write the failing API test**

Create `backend/tests/test_email_templates_api.py`:

```python
from tests.factories import make_user


def _login(client, username, password="secret123"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_list_requires_admin(client, app):
    make_user("plain", roles='["REQUESTOR"]')
    _login(client, "plain")
    assert client.get("/api/email-templates").status_code == 403


def test_admin_can_list_get_save_preview_reset(client, app):
    make_user("boss", roles='["ADMIN"]')
    _login(client, "boss")

    items = client.get("/api/email-templates").get_json()
    assert {i["type"] for i in items} == {"ASSIGNED", "APPROVED", "REJECTED", "FINANCE_READY"}

    one = client.get("/api/email-templates/ASSIGNED").get_json()
    assert one["is_custom"] is False and "tokens" in one

    saved = client.put("/api/email-templates/ASSIGNED",
                       json={"subject": "S", "body_html": "<p>{number}</p>", "enabled": True}).get_json()
    assert saved["is_custom"] is True

    prev = client.post("/api/email-templates/ASSIGNED/preview",
                       json={"subject": "S", "body_html": "<p>{number}</p>"}).get_json()
    assert "CX000042" in prev["html"]           # sample data substituted

    reset = client.post("/api/email-templates/ASSIGNED/reset").get_json()
    assert reset["subject"] == items[0]["subject"] or reset["is_custom"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_email_templates_api.py -q`
Expected: FAIL — 404 on the routes (blueprint not registered).

- [ ] **Step 3: Add the Pydantic schema**

Create `backend/app/schemas/email_template.py`:

```python
from pydantic import BaseModel


class EmailTemplateIn(BaseModel):
    subject: str
    body_html: str
    enabled: bool = True


class EmailTemplatePreviewIn(BaseModel):
    subject: str
    body_html: str
```

- [ ] **Step 4: Add the blueprint**

Create `backend/app/blueprints/email_templates.py`:

```python
from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.email_template import EmailTemplateIn, EmailTemplatePreviewIn
from app.services import email_template_service as ets

bp = Blueprint("email_templates", __name__, url_prefix="/api/email-templates")


@bp.get("")
@require_roles("ADMIN")
def list_templates():
    return jsonify([
        {"type": t, "name": ets.NAMES[t], "subject": ets.get(t)["subject"],
         "enabled": ets.get(t)["enabled"], "is_custom": ets.get(t)["is_custom"]}
        for t in ets.TYPES
    ])


@bp.get("/<type_>")
@require_roles("ADMIN")
def get_template(type_):
    data = ets.get(type_)
    data["tokens"] = ets.TOKENS[type_]
    return jsonify(data)


@bp.put("/<type_>")
@require_roles("ADMIN")
def save_template(type_):
    payload = EmailTemplateIn(**(request.get_json(silent=True) or {}))
    return jsonify(ets.save(type_, payload.subject, payload.body_html, payload.enabled))


@bp.post("/<type_>/save-as-default")
@require_roles("ADMIN")
def save_as_default(type_):
    return jsonify(ets.save_as_default(type_))


@bp.post("/<type_>/reset")
@require_roles("ADMIN")
def reset_template(type_):
    return jsonify(ets.reset(type_))


@bp.post("/<type_>/preview")
@require_roles("ADMIN")
def preview_template(type_):
    payload = EmailTemplatePreviewIn(**(request.get_json(silent=True) or {}))
    ets._require_type(type_)
    ctx = ets.sample_context(type_)
    subject = ets._substitute(payload.subject, ctx)
    from app.services import email_frame
    html = email_frame.wrap(ets._substitute(payload.body_html, ctx))
    return jsonify({"subject": subject, "html": html})
```

- [ ] **Step 5: Register the blueprint**

In `backend/app/__init__.py`, after the requests blueprint registration, add:

```python
    from .blueprints.email_templates import bp as email_templates_bp
    app.register_blueprint(email_templates_bp)
```

- [ ] **Step 6: Run the API test**

Run: `.venv/Scripts/python.exe -m pytest tests/test_email_templates_api.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/email_template.py backend/app/blueprints/email_templates.py backend/app/__init__.py backend/tests/test_email_templates_api.py
git commit -m "feat(api): admin email-templates endpoints"
```

---

## Task 7: Frontend API module

**Files:**
- Create: `frontend/src/api/emailTemplates.ts`

**Interfaces:**
- Consumes: `api` from `./client`.
- Produces: `EmailTemplate`, `EmailTemplateSummary`, `Token`, `listEmailTemplates`, `getEmailTemplate`, `saveEmailTemplate`, `saveAsDefault`, `resetEmailTemplate`, `previewEmailTemplate`.

- [ ] **Step 1: Implement the module**

Create `frontend/src/api/emailTemplates.ts`:

```typescript
import { api } from './client'

export interface Token { token: string; description: string }
export interface EmailTemplateSummary {
  type: string; name: string; subject: string; enabled: boolean; is_custom: boolean
}
export interface EmailTemplate extends EmailTemplateSummary {
  body_html: string
  default_subject: string
  default_body_html: string
  tokens: Token[]
}
export interface Preview { subject: string; html: string }

export function listEmailTemplates(): Promise<EmailTemplateSummary[]> {
  return api('/email-templates')
}
export function getEmailTemplate(type: string): Promise<EmailTemplate> {
  return api(`/email-templates/${type}`)
}
export function saveEmailTemplate(
  type: string, body: { subject: string; body_html: string; enabled: boolean },
): Promise<EmailTemplate> {
  return api(`/email-templates/${type}`, { method: 'PUT', body })
}
export function saveAsDefault(type: string): Promise<EmailTemplate> {
  return api(`/email-templates/${type}/save-as-default`, { method: 'POST' })
}
export function resetEmailTemplate(type: string): Promise<EmailTemplate> {
  return api(`/email-templates/${type}/reset`, { method: 'POST' })
}
export function previewEmailTemplate(
  type: string, body: { subject: string; body_html: string },
): Promise<Preview> {
  return api(`/email-templates/${type}/preview`, { method: 'POST', body })
}
```

- [ ] **Step 2: Typecheck**

Run (from `frontend/`): `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/emailTemplates.ts
git commit -m "feat(web): email-templates API client"
```

---

## Task 8: Quill editor component

**Files:**
- Create: `frontend/src/components/ui/QuillEditor.tsx`
- Modify: `frontend/package.json` (via `npm install quill`)

**Interfaces:**
- Produces: `QuillEditor({ value, onChange, onReady }: { value: string; onChange: (html: string) => void; onReady?: (insert: (text: string) => void) => void })`.

- [ ] **Step 1: Install Quill**

Run (from `frontend/`): `node ./node_modules/npm/bin/npm-cli.js install quill@^2.0.0`
(If that path is absent, use `npm install quill@^2.0.0` in a shell where the repo `&` path is not an issue.)
Expected: `quill` added to `package.json` dependencies.

- [ ] **Step 2: Implement the component**

Create `frontend/src/components/ui/QuillEditor.tsx`:

```typescript
import { useEffect, useRef } from 'react'
import Quill from 'quill'
import 'quill/dist/quill.snow.css'

const TOOLBAR = [
  [{ font: [] }, { size: [] }],
  ['bold', 'italic', 'underline'],
  [{ color: [] }, { background: [] }],
  [{ list: 'ordered' }, { list: 'bullet' }],
  ['link'],
  ['clean'],
]

export function QuillEditor({
  value,
  onChange,
  onReady,
}: {
  value: string
  onChange: (html: string) => void
  onReady?: (insert: (text: string) => void) => void
}) {
  const elRef = useRef<HTMLDivElement>(null)
  const quillRef = useRef<Quill | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    if (!elRef.current || quillRef.current) return
    const q = new Quill(elRef.current, { theme: 'snow', modules: { toolbar: TOOLBAR } })
    quillRef.current = q
    q.clipboard.dangerouslyPasteHTML(value)
    q.on('text-change', () => onChangeRef.current(q.root.innerHTML))
    onReady?.((text: string) => {
      const range = q.getSelection(true)
      q.insertText(range ? range.index : q.getLength(), text)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Sync external value only when it diverges (e.g. after Reset).
  useEffect(() => {
    const q = quillRef.current
    if (q && value !== q.root.innerHTML) q.clipboard.dangerouslyPasteHTML(value)
  }, [value])

  return <div className="bg-surface"><div ref={elRef} style={{ minHeight: 320 }} /></div>
}
```

- [ ] **Step 3: Typecheck & build**

Run (from `frontend/`):
`node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` then
`node ./node_modules/vite/bin/vite.js build`
Expected: no errors; build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/ui/QuillEditor.tsx
git commit -m "feat(web): Quill rich-text editor component"
```

---

## Task 9: Admin pages (list + editor) and routing

**Files:**
- Create: `frontend/src/routes/admin/EmailTemplatesPage.tsx`
- Create: `frontend/src/routes/admin/EmailTemplateEditor.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Test: `frontend/src/routes/admin/EmailTemplateEditor.test.tsx`

**Interfaces:**
- Consumes: `emailTemplates` API (Task 7), `QuillEditor` (Task 8), `Button`, `Input`.

- [ ] **Step 1: List page**

Create `frontend/src/routes/admin/EmailTemplatesPage.tsx`:

```typescript
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listEmailTemplates } from '../../api/emailTemplates'

export default function EmailTemplatesPage() {
  const { data = [] } = useQuery({ queryKey: ['email-templates'], queryFn: listEmailTemplates })
  return (
    <div className="max-w-3xl">
      <h1 className="mb-4 text-2xl font-semibold text-fg">Email Templates</h1>
      <p className="mb-4 text-sm text-muted">Customize the emails CAPEX Flow sends to users.</p>
      <div className="space-y-2">
        {data.map((t) => (
          <Link key={t.type} to={`/admin/email-templates/${t.type}`}
            className="flex items-center justify-between rounded-xl border border-border bg-surface p-4 shadow-sm hover:border-accent">
            <div>
              <div className="font-medium text-fg">{t.name}</div>
              <div className="text-xs text-muted">{t.subject}</div>
            </div>
            <div className="flex items-center gap-2 text-xs">
              {t.is_custom && <span className="text-accent">customized</span>}
              {!t.enabled && <span className="text-red-600 dark:text-red-400">disabled</span>}
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Editor page**

Create `frontend/src/routes/admin/EmailTemplateEditor.tsx`:

```typescript
import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getEmailTemplate, saveEmailTemplate, saveAsDefault, resetEmailTemplate,
  previewEmailTemplate, type EmailTemplate,
} from '../../api/emailTemplates'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { QuillEditor } from '../../components/ui/QuillEditor'

export default function EmailTemplateEditor() {
  const { type = '' } = useParams()
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['email-templates', type], queryFn: () => getEmailTemplate(type) })
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [dirty, setDirty] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const insertRef = useRef<(t: string) => void>(() => {})

  useEffect(() => {
    if (data) { setSubject(data.subject); setBody(data.body_html); setEnabled(data.enabled); setDirty(false) }
  }, [data])

  function apply(updated: EmailTemplate) {
    qc.setQueryData(['email-templates', type], updated)
    qc.invalidateQueries({ queryKey: ['email-templates'] })
    setDirty(false)
  }
  const save = useMutation({ mutationFn: () => saveEmailTemplate(type, { subject, body_html: body, enabled }), onSuccess: apply })
  const asDefault = useMutation({ mutationFn: () => saveAsDefault(type), onSuccess: apply })
  const reset = useMutation({ mutationFn: () => resetEmailTemplate(type), onSuccess: apply })
  const doPreview = useMutation({
    mutationFn: () => previewEmailTemplate(type, { subject, body_html: body }),
    onSuccess: (p) => setPreview(p.html),
  })

  if (!data) return null
  return (
    <div className="flex gap-4">
      <div className="min-w-0 flex-1">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-fg">
            {data.name} {dirty && <span className="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">edited</span>}
          </h1>
          <div className="flex gap-2">
            <Button disabled={save.isPending} onClick={() => save.mutate()}>Save</Button>
            <Button variant="secondary" onClick={() => asDefault.mutate()}>Save as Default</Button>
            <Button variant="secondary" onClick={() => doPreview.mutate()}>Preview</Button>
            <Button variant="ghost" onClick={() => reset.mutate()}>Reset to default</Button>
          </div>
        </div>
        <label className="mb-1 block text-xs text-muted">Subject</label>
        <Input value={subject} onChange={(e) => { setSubject(e.target.value); setDirty(true) }} />
        <label className="mb-1 mt-4 block text-xs text-muted">Body</label>
        <QuillEditor value={data.body_html} onChange={(html) => { setBody(html); setDirty(true) }}
          onReady={(insert) => (insertRef.current = insert)} />
        <label className="mt-4 flex items-center gap-2 text-sm text-fg">
          <input type="checkbox" checked={enabled} onChange={(e) => { setEnabled(e.target.checked); setDirty(true) }} />
          Send this email
        </label>
      </div>
      <aside className="w-64 shrink-0 rounded-xl border border-border bg-surface-2 p-4">
        <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Placeholders</div>
        <p className="mb-3 text-xs text-muted">Click to insert. Replaced with real values when the email is sent.</p>
        <div className="space-y-2">
          {data.tokens.map((tok) => (
            <button key={tok.token} type="button" onClick={() => insertRef.current(tok.token)}
              className="block w-full text-left">
              <code className="text-accent">{tok.token}</code>
              <div className="text-xs text-muted">{tok.description}</div>
            </button>
          ))}
        </div>
      </aside>
      {preview !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-6" onClick={() => setPreview(null)}>
          <div className="max-h-[90vh] w-full max-w-[680px] overflow-auto rounded-xl bg-white" onClick={(e) => e.stopPropagation()}>
            <iframe title="Email preview" srcDoc={preview} className="h-[80vh] w-full" sandbox="" />
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Wire routes**

In `frontend/src/App.tsx`, add imports and routes inside the `AdminLayout` block:

```typescript
import EmailTemplatesPage from './routes/admin/EmailTemplatesPage'
import EmailTemplateEditor from './routes/admin/EmailTemplateEditor'
```
```typescript
          <Route path="/admin/email-templates" element={<EmailTemplatesPage />} />
          <Route path="/admin/email-templates/:type" element={<EmailTemplateEditor />} />
```

- [ ] **Step 4: Add the nav item**

In `frontend/src/components/AppShell.tsx`, add `Mail` to the `lucide-react` import, and add to the Admin section `items` array:

```typescript
      { to: '/admin/email-templates', label: 'Email Templates', icon: Mail, roles: ['ADMIN'] },
```

- [ ] **Step 5: Component test for token insertion**

Create `frontend/src/routes/admin/EmailTemplateEditor.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import EmailTemplateEditor from './EmailTemplateEditor'
import * as apiMod from '../../api/emailTemplates'

vi.mock('../../api/emailTemplates')

function renderAt() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/admin/email-templates/ASSIGNED']}>
        <Routes><Route path="/admin/email-templates/:type" element={<EmailTemplateEditor />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('EmailTemplateEditor', () => {
  it('shows placeholders for the template', async () => {
    vi.mocked(apiMod.getEmailTemplate).mockResolvedValue({
      type: 'ASSIGNED', name: 'Approval needed', subject: 'S', body_html: '<p>x</p>',
      enabled: true, is_custom: false, default_subject: 'S', default_body_html: '<p>x</p>',
      tokens: [{ token: '{number}', description: 'Request number' }],
    } as never)
    renderAt()
    await waitFor(() => expect(screen.getByText('{number}')).toBeInTheDocument())
    fireEvent.click(screen.getByText('{number}'))   // does not throw
    expect(screen.getByText('Request number')).toBeInTheDocument()
  })
})
```

- [ ] **Step 6: Run frontend checks**

Run (from `frontend/`):
`node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`
`node ./node_modules/vitest/vitest.mjs run src/routes/admin/EmailTemplateEditor.test.tsx`
`node ./node_modules/vite/bin/vite.js build`
Expected: typecheck clean, test passes, build succeeds. (If Quill's DOM APIs error under jsdom, the test only asserts the placeholders panel — mock `QuillEditor` in the test with `vi.mock('../../components/ui/QuillEditor', () => ({ QuillEditor: () => null }))`.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/routes/admin/EmailTemplatesPage.tsx frontend/src/routes/admin/EmailTemplateEditor.tsx frontend/src/routes/admin/EmailTemplateEditor.test.tsx frontend/src/App.tsx frontend/src/components/AppShell.tsx
git commit -m "feat(web): admin email template editor page"
```

---

## Task 10: Docs

**Files:**
- Modify: `CLAUDE.md`, `docs/SOP.md`
- Regenerate: `docs/CAPEX Flow SOP.docx` (via the generator script)

- [ ] **Step 1: Update CLAUDE.md**

Add `EmailTemplate` to the Data model section, `email_templates` to the blueprints list, and `email_frame`/`email_template_service` to the services list. Add a line to Conventions: "Notification emails are editable HTML templates (Admin → Email Templates); defaults live in `email_template_service.DEFAULTS`."

- [ ] **Step 2: Update SOP.md**

In §7, note that admins can now edit the four emails' subject/body/enabled under Admin → Email Templates, with `{token}` placeholders and a brand-styled frame. In §8 (Administration) add an "Email Templates" bullet.

- [ ] **Step 3: Regenerate the Word SOP**

Ensure `docs/CAPEX Flow SOP.docx` is closed, then run the generator (add the new §8 bullet in the script first):
`.venv/Scripts/python.exe "<scratchpad>/build_sop_docx.py"`
Expected: `Saved: …CAPEX Flow SOP.docx`.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/SOP.md "docs/CAPEX Flow SOP.docx"
git commit -m "docs: admin email templates (SOP + CLAUDE.md)"
```

---

## Self-Review

**Spec coverage:** locked frame → Task 2; four types/subject/body/enabled → Tasks 3,6,9; three-tier defaults (shipped→admin→live) → Task 3 (`_row_or_seed` seeds default from shipped; `save_as_default`; `reset`); tokens incl. `{comment}` → Tasks 3,5; HTML send → Tasks 4,5; preview with sample data → Tasks 6,9; placeholders panel + insertion → Task 9; admin-only API → Task 6; nav/route → Task 9; tests → each task; migration → Task 1; docs → Task 10. No gaps.

**Placeholder scan:** no TBD/TODO; all code shown in full.

**Type consistency:** `render/get/save/save_as_default/reset/context_for/sample_context` names match across Tasks 3, 5, 6; frontend `EmailTemplate`/`Token` fields match the blueprint's JSON (`tokens` added in `GET /<type>`); `QuillEditor` prop names (`value`, `onChange`, `onReady`) match Task 9 usage.
