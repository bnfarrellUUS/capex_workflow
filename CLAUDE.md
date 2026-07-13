# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# Project: CAPEX Flow

Internal web app for **United Uptime Services** to submit, route, approve, and
search capital-expenditure (CAPEX) requests. Product brand name: **CAPEX Flow**
(under "United Uptime Services").

## Stack

- **backend/** — Flask API (Python 3.14), SQLAlchemy 2.0 (typed `Mapped`),
  Flask-Login session auth + CSRF (login sets a 30-day remember-me cookie so
  email deep links survive browser restarts; `REMEMBER_COOKIE_*` in config),
  Pydantic v2 request schemas, Alembic migrations. **SQLite** in dev (`backend/instance/capex_dev.db`), **Azure SQL
  Server** in prod.
- **frontend/** — React 19 + Vite 6 + TypeScript SPA. React Router 7, TanStack
  Query 5, Tailwind CSS v4, `lucide-react` icons. **Single-server:** the SPA is
  built (`vite build` → `frontend/dist`) and served by Flask itself — the app
  runs as one server on `http://localhost:5000` (Flask serves `dist` plus the
  `/api` routes; a catch-all returns `index.html` for client-side routes). The
  API client uses relative `/api`, so it's same-origin. There is no Vite dev
  proxy.

## Running the app

**Windows gotcha:** the repo path contains `&` (`D&H United Fueling Solutions`),
which breaks npm's default cmd script-shell and breaks running `npm run …`
through tools that shell out. Two consequences:
- Double-click **`Start CAPEX Flow.cmd`** (repo root), or run **`run-app.ps1`**
  from a PowerShell prompt (`powershell -ExecutionPolicy Bypass -File
  .\run-app.ps1` if script execution is blocked). It does first-run setup (venv,
  deps, `flask db upgrade`, `python seed.py`), **builds the frontend**, starts
  the single Flask server (`flask run`, port 5000) in its own window, and opens
  the browser to `http://localhost:5000`. It launches the server from its own
  directory via a *relative* path so the `&`-in-path never reaches a parser.
  (A prior `run-app.bat` was removed — cmd's `start cmd /k` mis-parses the `&`
  in the path, flashing the windows closed.)
- When running frontend tooling directly (CI, agents), call the binaries via
  node to sidestep the shell: e.g.
  `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`,
  `node ./node_modules/vite/bin/vite.js build`,
  `node ./node_modules/vitest/vitest.mjs run`.

Manual start:

    # build the frontend (served by Flask)
    cd frontend && npm install && node ./node_modules/vite/bin/vite.js build
    # backend serves the SPA + API on one port
    cd ../backend && python -m venv .venv && source .venv/Scripts/activate
    pip install -r requirements.txt && flask db upgrade && python seed.py && flask run

App: http://localhost:5000 (`GET /api/health` → `{"status":"ok"}`) ·
Dev login: **admin / ChangeMe123!**
(To iterate on the frontend, rebuild with `node ./node_modules/vite/bin/vite.js
build`; there is no live dev server.)

## Testing

- Backend: `cd backend && pytest -q` (currently 111 tests).
- Frontend: `npm test` (vitest) and `npm run build`; typecheck with `tsc`.
- Always run backend pytest + frontend typecheck after changes touching either.

## Backend layout (`backend/app/`)

- `models/__init__.py` — all SQLAlchemy models (see Data model below).
- `blueprints/` — HTTP routes, one per resource, each mounted under `/api/...`:
  `health`, `auth` (`/api/auth`), `users`, `divisions`, `thresholds`,
  `profile`, `requests`, `email_templates` (`/api/email-templates`, ADMIN-only).
  Routes are thin; they validate input with Pydantic schemas and delegate to
  services.
- `services/` — business logic: `request_service`, `workflow_service`
  (approval routing), `auth_service`, `user_service`, `division_service`,
  `threshold_service`, `profile_service`, `attachment_service`/`storage`,
  `counter_service` (request numbers `CX000001…`), `notify` (writes
  `NotificationLog`, renders emails via templates), `email_template_service`
  (four editable email templates: defaults, tokens, render, three-tier reset),
  `email_frame` (brand HTML wrapper; the rounded chrome — header band, CTA
  buttons, bottom strip — is baked into `assets/*.png` because classic
  Outlook's Word engine can't round CSS corners and mangles VML on send),
  `email_outlook` (Outlook COM sender; attaches referenced `cid:capexflow-*`
  assets), `security`, `errors` (`ServiceError(msg, status)`).
  **Email gotchas:** editable template bodies must stay Quill-round-trippable
  (no tables/bgcolor/VML — Quill strips them); preview HTML must equal sent
  HTML (test-pinned); verify email changes against a real Outlook render, not
  just the browser.
- `schemas/request.py` — Pydantic v2 input models. **Important:** the PATCH
  route builds `RequestDraft(**json).model_dump(exclude_unset=True)`, so a field
  absent from `RequestDraft` is silently dropped even if the model/serializer
  support it. Add new editable fields to this schema.
- `serialization.py` (`money_str`), `authz.py`, `roles.py`, `config.py`,
  `extensions.py` (`db`, login manager, CSRF).

## Data model (`capex_requests` is the core)

- **User** — `username`, `email`, `name`, `password_hash`, `roles` (JSON string
  array, see Roles), `active`, `division_id`, `delegate_id` (out-of-office
  delegate), lockout fields, reset token. `roles_list` property parses roles.
- **Division** — `number`, `name`, `active`, `l1_approvers` (many-to-many via
  `division_l1_approvers`: the Level-1 approver pool for its requests).
- **ApprovalThreshold** — one row per `level` (1/2/3), `max_amount` (top level
  usually null = no cap), `approvers` (many-to-many via `threshold_approvers`:
  the L2/L3 approver pool; L1 comes from the division). Each level can have
  multiple approvers and **any one** may act.
- **CapexRequest** — `number`, `status`, `requestor_id`, `assignee_id` (current
  approver), `division_id`, `request_date`; Basic-info flags (`budgeted`,
  `replacement`, `health_safety`, `revenue_generating`, `environmental`,
  `competitive_bids`, `lease_recommended`); narrative (`justification`,
  `effect_on_operations`); economic fields (`asset_life`, `irr_after_tax`,
  `first_year_ebit`, `annual_savings`, `payback_years`, `npv_savings`); finance
  cost breakdown (`cost_*`, `finance_completed`); `total_cost`,
  `required_levels`, `current_level`. Money = `Numeric(18,2)`, ratios =
  `Numeric(9,4)`.
- **EquipmentItem** — line items (`units`, `condition` NEW/USED, `type`, `make`,
  `model`, `cost`); sum drives `total_cost`.
- **Attachment**, **ApprovalAction** (audit trail: SUBMITTED/APPROVED/REJECTED/
  RESUBMITTED/FINANCE_COMPLETED, with `level`, `comment`, `acted_for_id` for
  delegated actions), **NotificationLog**, **Counter**, **AppSetting**.
- **EmailTemplate** — one row per email `type` (ASSIGNED/APPROVED/REJECTED/
  FINANCE_READY): live `subject`/`body_html`/`enabled` plus `default_subject`/
  `default_body_html` (admin-set baseline). A row exists only once customized;
  code holds the shipped defaults (`email_template_service.DEFAULTS`).

## Roles & approval workflow

Roles: **REQUESTOR**, **APPROVER**, **FINANCE**, **ADMIN** (a user may hold
several).

Status flow: `DRAFT` → `PENDING_L1` → `PENDING_L2` → `PENDING_L3` → `APPROVED`,
with `REJECTED` as a side state (a rejected request can be resubmitted by its
owner). Owners can delete their own drafts (`DELETE /api/requests/<id>`,
DRAFT-only; removes stored attachment files, children cascade) — the red
"Delete draft" action on the request detail page. The number of levels required (`required_levels`) is derived from
`total_cost` vs the `ApprovalThreshold` caps. Each level has a **pool** of
approvers (L1 from the request's division, L2/L3 from the threshold rows), each
mapped through their out-of-office delegate; **any one** eligible approver may
approve (advances) or reject. The pool appears on every member's "assigned"
worklist; `assignee_id` is just a display hint (the first current approver).
After final approval, a **FINANCE** user completes the cost breakdown
(`cost_*` → `finance_completed`).

Each transition sends a notification email (assignment/decision/finance-ready).
Emails are **editable HTML templates** — admins customize the subject, body
(WYSIWYG), and enabled flag per type under **Admin → Email Templates**, with
`{token}` placeholders substituted at send time and a brand-styled locked frame.
Sent via the local Outlook desktop app (`email_outlook`); redirected to
`EMAIL_REDIRECT_TO` while testing. Defaults live in
`email_template_service.DEFAULTS`.

## Frontend layout (`frontend/src/`)

- `main.tsx` (query client, 401 → redirect to /login), `App.tsx` (routes),
  `index.css` (Tailwind v4 + design tokens + dark variant).
  `auth/loginRedirect.ts` — deep-link preservation: unauthenticated visits
  redirect to `/login?next=<path>` (set by `ProtectedLayout` and the 401
  handler in `main.tsx`); `LoginPage` navigates to the sanitized `next`
  (same-app absolute paths only) after sign-in.
- `components/AppShell.tsx` — navy grouped sidebar (icons, active pill) + header
  (theme toggle, Sign Out). `components/ui/` — `Button` (variants
  primary/secondary/ghost), `Input`, `Select`, `PasswordInput` (eye toggle),
  `Card`/`StatCard`, `Badge`/`StatusBadge`, `TransferList` (dual-listbox:
  Available | Add»/«Remove | Selected + ▲▼ reorder), `BrandCard` (email-look
  page card: navy header band + per-page mark (the page's own nav icon in a
  sky-blue rounded tile) + title/sky subtitle, optional actions/subheader/
  footer slots — one per page; used by Dashboard, Requests list/detail, Wizard,
  Profile, and the admin list pages. `mark` prop is a page key —
  `dashboard`/`newRequest`/`requests`/`users`/`divisions`/`thresholds`/
  `emailTemplates`/`profile` — mapped to the matching `NavIcons`), `QuillEditor`.
  `components/NavIcons.tsx` (custom per-page sidebar line-icons — one distinct
  symbol per nav item, 24px grid / rounded joins, `currentColor`; from
  `brand/UUS CAPEX Flow Nav Icons.html`. AppShell uses these instead of
  lucide for nav; lucide still supplies non-nav glyphs like Sign Out).
  `components/ActionIcons.tsx` (same-style in-page icons from the same doc:
  approval actions Approve/Reject/Submit, row controls View/Edit/Delete/
  Download/Search/Filter/Add/Upload, and workflow-status icons. Used by
  `StatusBadge` (icon inside each pill), RequestDetailPage action buttons,
  the Wizard, and the Requests list. `currentColor`, so each icon takes its
  button/badge color).
  `components/Logo.tsx` (primary Capital-Cycle mark, used in the sidebar/login).
  `components/BrandMark.tsx` (the four brand logo marks — cycle/ascent/check/
  uptime; kept as a brand asset but no longer wired into BrandCard, which now
  uses per-page `NavIcons` marks). `ThemeToggle.tsx`, `theme.ts`.
- `routes/` — `DashboardPage` (KPI StatCards + approvals table), `LoginPage`,
  `RequestsListPage` (+ shared `RequestsTable`: sortable column headers and a
  trailing per-row View action; client-side, comparators + `filterRequests`
  in `routes/requestsSort.ts` — status sorts in workflow order, blanks last;
  the list page adds a client-side search box over number/division/requestor),
  `NewRequestPage` (creates a
  draft then redirects to the wizard), `WizardPage` (6-step request wizard:
  Basic Info, Description, Effect on Ops, Equipment, Economic, Review — styled
  as an email-look brand card: navy header band with Logo, numbered stepper
  [✓ done / accent active], footer action bar; stepper clicks save the draft
  before jumping. The wizard edits both DRAFT and REJECTED requests (owners can
  fix a rejected request and resubmit); the Review-step action calls `resubmit`
  when the loaded request is REJECTED, otherwise `submit`), `RequestDetailPage`,
  `ProfilePage`, and `routes/admin/` (Users, Divisions, Approval Thresholds,
  Email Templates + forms). The Email Templates editor uses `components/ui/
  QuillEditor` (Quill 2.x on a ref) with a placeholders panel and a sandboxed
  iframe preview, and a tab bar (`TemplateTabs`) across the top to switch
  between the four templates in place — switching while there are unsaved
  edits prompts a discard confirm. (The list page is still the sidebar
  landing.) Approver pools (division L1, threshold L2/L3) and user roles
  are assigned with the `TransferList` dual-listbox, not checkboxes.
  `routes/wizard/types.ts` maps API ↔ form (`toForm`/`toPayload`).
- `api/` — `client.ts` (fetch wrapper; obtains CSRF from `/api/auth/csrf`, sends
  `X-CSRFToken` on mutations, `credentials: 'include'`), plus per-resource
  modules (`auth`, `requests`, `divisions`, `users`, `thresholds`, `profileApi`).

## Design system & brand

- **Theming:** semantic Tailwind tokens (`bg`, `surface`, `surface-2`, `border`,
  `fg`, `muted`, `sidebar`, `accent`) defined in `index.css`; dark mode is a
  class-based `@custom-variant dark` that overrides the same variables. Prefer
  these tokens over hard-coded `slate-*`. Theme persists in
  `localStorage['capex-theme']`; an inline script in `index.html` applies it
  before render to avoid a flash.
- **Page pattern:** every main page wraps its content in **one `BrandCard`**
  (email-look card: navy `#0B2A4A` header band + per-page mark (the page's nav
  icon, sky-blue in a rounded tile) + white title + sky `#93BBF5` subtitle;
  optional `actions`/`subheader`/`footer` slots). New pages should follow this
  and pass the matching page `mark` (`dashboard`/`newRequest`/`requests`/
  `users`/`divisions`/`thresholds`/`emailTemplates`/`profile`).
  Secondary edit forms (User/Division forms, EmailTemplateEditor) keep plain
  headings.
- **Brand (`brand/`, "UUS CAPEX Flow"):** `brand_asset.pdf` plus
  `UUS CAPEX Flow - Logo.dc.html` (the four logo-direction mockups; the old
  ARIA placeholder assets were removed once these landed). Palette navy
  `#0B2A4A`, blue `#2563EB`, sky `#93BBF5`. Logo mark = direction **1d
  "Capital Cycle"** (`components/Logo.tsx` + `public/favicon.svg`). No IBM
  Plex typeface (default system font). The look-and-feel targets the "ARIA"
  reference dashboard.

## Conventions & gotchas

- **After each significant change, update the docs and commit.** Keep this
  CLAUDE.md (and any relevant `docs/superpowers/specs/`) in sync with the code,
  then make a focused git commit with a clear message describing what changed
  and how it was verified. Don't batch several unrelated changes into one commit.
- Keep routes thin; put logic in `services/`. Raise `ServiceError(msg, status)`
  for handled API errors.
- New editable request fields must be added in **all** of: model, `request_out`
  serializer, `RequestDraft` schema, frontend `CapexRequestData`/`RequestForm`,
  and `toForm`/`toPayload` — missing the Pydantic schema silently drops the field.
- `docs/superpowers/specs/` holds design specs; milestone/phase plans live under
  `docs/`.
