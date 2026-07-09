# Design: Admin Email Template Editor

**Date:** 2026-07-09
**Status:** Approved (pending spec review)

## Overview

Add an admin-only WYSIWYG editor that lets administrators customize the four
notification emails CAPEX Flow sends. Today those bodies/subjects are hard-coded
plain-text strings in `services/notify.py`. This feature moves the wording and
formatting into editable, brand-styled HTML templates stored in the database,
while the routing logic (who is notified, when) stays exactly as it is.

The four email types:

| Type | Sent when | Recipient |
|------|-----------|-----------|
| `ASSIGNED` | Submit, advance to next level, resubmit | Each eligible approver in the current level's pool |
| `APPROVED` | Final approval | Requestor |
| `REJECTED` | Reject | Requestor |
| `FINANCE_READY` | Final approval | All active Finance users |

## Goals

- Admins edit each email's **subject** (plain text + tokens), **body** (WYSIWYG
  HTML + tokens), and an **enabled** toggle.
- Emails render as **branded HTML** using a locked frame (admins can't break the
  header/footer or branding).
- Three-tier template state per type: **shipped default** (in code) →
  **admin default** (captured via *Save as Default*) → **live** (edited via
  *Save*). *Reset to default* reverts live to the admin default (or the shipped
  default if none was ever captured).
- **Preview** renders the draft being edited with realistic sample data.
- A **placeholders panel** lists the tokens available for each template; clicking
  one inserts it at the cursor.

## Non-goals (YAGNI)

- Creating arbitrary new template types (there are exactly four).
- Approve/reject directly from the email (token-authenticated action links).
- Per-division or per-user template variants.
- Image uploads, attachments, or the logo graphic in the email (brand is
  conveyed with colors + wordmark; see Branding).
- Template version history / audit of edits beyond `updated_at`.

## Branding & the locked frame

Emails become **HTML** (sent via Outlook `.HTMLBody`). A code-defined HTML shell
wraps the admin's body content:

- **Header band:** navy `#0B2A4A`, white wordmark "United Uptime Services" with
  "CAPEX Flow" subtitle. No image — text + color only, so it renders identically
  in Outlook desktop, the browser preview, and all clients.
- **Body region:** the admin's rendered HTML.
- **Footer:** small muted line ("Automated message from CAPEX Flow — do not
  reply").
- **Accent palette:** links/buttons blue `#2563EB`, hairlines/accents sky
  `#93BBF5`. All styling is **inline CSS** (email-client requirement).
- **Redirect banner:** when `EMAIL_REDIRECT_TO` is set, a yellow bar is prepended
  inside the frame noting the intended recipient (replaces today's
  `[Intended recipient: …]` plain-text prefix).

The frame lives in `services/email_frame.py` as `wrap(body_html, *, redirect_note=None) -> str`.

## Tokens

Tokens use `{token}` syntax and are substituted at render time. Unknown tokens are
left intact (so a typo is visible, not silently dropped).

| Token | Meaning | Templates |
|-------|---------|-----------|
| `{number}` | Request number (CX000042) | all |
| `{requestor}` | Requestor name | all |
| `{division}` | "12 — Field Services" | all |
| `{total_cost}` | "$182,400.00" | all |
| `{link}` | Deep link to the request (uses `APP_BASE_URL`) | all |
| `{level}` | "Level 2 of 3" | `ASSIGNED` |
| `{comment}` | Reviewer's rejection comment | `REJECTED` |

`{comment}` requires threading the reject comment into `notify_decision` — a
small change in `blueprints/requests.py` (reject route) and `notify.py`.

## Data model

New model `EmailTemplate` (table `email_templates`) + Alembic migration:

| Column | Type | Notes |
|--------|------|-------|
| `type` | `String(20)` PK | ASSIGNED / APPROVED / REJECTED / FINANCE_READY |
| `subject` | `Text` | live subject |
| `body_html` | `Text` | live body |
| `enabled` | `Boolean` default true | |
| `default_subject` | `Text` | admin-set default subject |
| `default_body_html` | `Text` | admin-set default body |
| `updated_at` | `DateTime` | |

A row exists only once an admin has saved. Absent a row, both live and default
fall back to the **shipped default** defined in code.

## Backend

### `services/email_template_service.py`
- `DEFAULTS: dict[type, {subject, body_html}]` — the shipped defaults (HTML
  bodies mirroring today's enriched plain-text emails).
- `TOKENS: dict[type, list[{token, description}]]` — placeholder metadata for the
  panel.
- `get(type) -> {type, subject, body_html, enabled, default_subject, default_body_html, is_custom}`
  — merges the row (if any) over the shipped default.
- `save(type, subject, body_html, enabled)` — upsert live fields.
- `save_as_default(type)` — copy current live → default fields.
- `reset(type)` — copy default (row default, else shipped) → live fields.
- `render(type, context) -> {subject, html}` — token-substitute subject + body,
  then `email_frame.wrap` the body. Raises nothing on missing tokens.
- `sample_context(type) -> dict` — realistic sample values for preview.
- `context_for(req, **extra) -> dict` — build the token context from a real
  `CapexRequest` (used by `notify.py`).

### `services/notify.py`
- Replace the hard-coded subject/body construction in `notify_assignment`,
  `notify_decision`, `notify_finance_ready` with
  `email_template_service.render(type, context_for(req, …))`.
- Skip sending when the template's `enabled` is false.
- Keep the always-write `NotificationLog` behavior and best-effort delivery.

### `services/email_outlook.py`
- `send(to, subject, body, html=None)` — if `html` is provided, set
  `mail.HTMLBody = html`; else keep `mail.Body = body` (plain-text fallback).

### `blueprints/email_templates.py` (ADMIN-only, mounted `/api/email-templates`)
- `GET  /api/email-templates` → list of 4: `{type, name, subject, enabled, is_custom}`.
- `GET  /api/email-templates/<type>` → full record + token metadata.
- `PUT  /api/email-templates/<type>` → save live `{subject, body_html, enabled}`.
- `POST /api/email-templates/<type>/save-as-default` → promote live to default.
- `POST /api/email-templates/<type>/reset` → revert live to default.
- `POST /api/email-templates/<type>/preview` `{subject, body_html}` → render the
  **draft** (unsaved) with sample data → `{subject, html}`.

Authz: reuse the existing admin guard pattern (as in users/divisions/thresholds
blueprints). Pydantic schema `EmailTemplateIn` for PUT/preview.

## Frontend

- **Nav:** add "Email Templates" under Admin (AdminLayout sidebar), icon
  `Mail` (lucide).
- **Route:** `/admin/email-templates` and `/admin/email-templates/:type`.
- **`EmailTemplatesPage`:** left list of the four templates (name + "customized"
  hint); selecting one routes to the editor.
- **`EmailTemplateEditor`:** matches the mockup —
  - Header: template name + "edited" badge (dirty state) + buttons **Save**,
    **Save as Default**, **Preview**, **Reset to default**.
  - **Subject** input (plain text, token-aware).
  - **Quill** editor (installed via `npm install quill`, instantiated directly
    on a ref — no React wrapper) with the full toolbar from the mockup: font
    family, size, bold/italic/underline, color, highlight, ordered/unordered
    lists, link. Content is HTML bound to `body_html`.
  - **Placeholders panel** (right): tokens for this template; click inserts at
    the cursor.
  - **Preview:** modal rendering the backend `preview` HTML in a sandboxed
    `<iframe srcdoc=…>`.
- **API module:** `api/emailTemplates.ts` mirroring the endpoints; TanStack Query
  for load/save with cache invalidation.
- Buttons use existing `Button` variants; styling uses the semantic tokens.

## Testing

**Backend (pytest):**
- `render` substitutes each token; unknown token left intact; frame wraps body;
  redirect banner appears when `EMAIL_REDIRECT_TO` set.
- `save` / `save_as_default` / `reset` state transitions (live vs default vs
  shipped fallback; `is_custom` flips correctly).
- Disabled template ⇒ `notify_*` records `NotificationLog` but does not send.
- `notify_assignment` uses rendered subject/body (deep link + level present).
- API: admin-only (403 for non-admin), PUT round-trips, preview renders draft,
  reset reverts.

**Frontend:**
- `tsc` typecheck + `npm run build`.
- Component test: clicking a placeholder inserts the token into the editor;
  dirty state toggles the "edited" badge.

## Migration & docs

- Alembic migration for `email_templates`.
- Update `CLAUDE.md` (data model + blueprints list + services), `docs/SOP.md`
  §7 (admins can now edit the emails), and regenerate the Word SOP.

## Config touchpoints

- No new config. Reuses `APP_BASE_URL`, `EMAIL_ENABLED`, `EMAIL_REDIRECT_TO`.
