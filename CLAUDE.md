# CLAUDE.md

Coding rules: @CODING-RULES.md

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
  (Don't recreate a `.bat` launcher — cmd's `start` mis-parses the `&` in the
  path.)
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
Dev login: **admin@uniteduptime.com / ChangeMe123!**
(To iterate on the frontend, rebuild with `node ./node_modules/vite/bin/vite.js
build`; there is no live dev server.)

## Testing

- Backend: `cd backend && pytest -q` (currently 164 tests).
- Frontend: `npm test` (vitest) and `npm run build`; typecheck with `tsc`.
- Always run backend pytest + frontend typecheck after changes touching either.

## Backend layout (`backend/app/`)

- `models/__init__.py` — all SQLAlchemy models (see Data model below).
- `blueprints/` — HTTP routes, one per resource, each mounted under `/api/...`:
  `health`, `auth` (`/api/auth`, email-based login plus `set-password`),
  `users`, `divisions`, `thresholds`, `profile`, `requests`, `email_templates`
  (`/api/email-templates`, ADMIN-only). Routes are thin; they validate input
  with Pydantic schemas and delegate to services. A flagged
  `must_change_password` user is blocked from the rest of the API by an
  app-level `before_request` (403 `PASSWORD_CHANGE_REQUIRED`), exempting only
  `auth.set_password`/`auth.me`/`auth.csrf_token`/`auth.logout`.
- `services/` — business logic: `request_service`, `workflow_service`
  (approval routing), `auth_service`, `user_service`, `division_service`,
  `threshold_service`, `profile_service`, `attachment_service`/`storage`,
  `counter_service` (request numbers `CX000001…`), `notify` (writes
  `NotificationLog`, renders emails via templates; asks `settings_service`
  for the delivery mode to pick the recipient), `settings_service`
  (app-wide settings in the `AppSetting` table — the email delivery mode:
  Test redirects all mail to a test recipient, Live sends to real
  recipients; defaults to Test + `EMAIL_REDIRECT_TO`), `email_template_service`
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

- **User** — `email`, `name`, `password_hash`, `must_change_password`, `roles`
  (JSON string array, see Roles), `active`, `division_id`, `delegate_id`
  (out-of-office delegate), lockout fields, reset token. `roles_list` property
  parses roles.
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
  cost breakdown (`cost_*`, asset details `asset_number`/`gl_account`/
`po_number`/`in_service_date`, `finance_completed`); `total_cost`,
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
several). New users and admin password resets start at `DEFAULT_PASSWORD`
(`Welcome@1` in `backend/app/config.py`) with `must_change_password` set,
forcing the Set-your-new-password screen on next sign-in.

Status flow: `DRAFT` → `PENDING_L1` → `PENDING_L2` → `PENDING_L3` → `APPROVED`,
with `REJECTED` as a side state (the owner can fix and resubmit via the wizard).
Owners can delete their own drafts (`DELETE /api/requests/<id>`, DRAFT-only;
removes stored attachment files, children cascade). `required_levels` is
derived from `total_cost` vs the `ApprovalThreshold` caps. Each level has a
**pool** of approvers (L1 from the request's division, L2/L3 from the threshold
rows), each mapped through their out-of-office delegate; **any one** eligible
approver may approve (advances) or reject. The pool appears on every member's
"assigned" worklist; `assignee_id` is just a display hint (the first current
approver).

After final approval, a **FINANCE** user completes the cost breakdown
(`cost_*` → `finance_completed`) and can re-save it anytime while the request
is APPROVED (each save logs a `FINANCE_COMPLETED` action). On the request
detail page: the breakdown is read-only to all viewers of an approved request;
FINANCE users get the form prefilled with decimal text inputs (dollar amounts;
client-side validated in `routes/financeCosts.ts` — accepts `$`/commas, names
the bad field on error); both views show a live **breakdown total vs. CAPEX
total** line (`BreakdownTotal`; cents math in `financeTotalCents` — green
"✓ Matches" or the amber difference) plus the asset detail fields. The page
also shows the approval history table (local-time Date column; `created_at`
treated as UTC) and a collapsed-by-default "Full request details" toggle
(`FullDetails`) exposing everything captured in the wizard. Attachment
permissions (`attachment_service._can_modify`): the requestor manages
attachments while DRAFT/REJECTED; FINANCE once APPROVED. Attach-file UI
(wizard + detail page) is a button over a hidden file input — picking a file
uploads immediately.

Each transition sends a notification email (assignment/decision/finance-ready)
via the local Outlook desktop app (`email_outlook`). Emails are **editable
HTML templates** — admins customize subject, body (WYSIWYG), and enabled flag
per type under **Admin → Email Templates**, with `{token}` placeholders
substituted at send time and a brand-styled locked frame. A runtime **delivery
mode** (Test/Live — toggled from the Email Templates page and editor via
`components/admin/EmailDeliveryMode.tsx`, stored in `AppSetting`, exposed at
`GET/PUT /api/email-templates/settings`) picks the recipient: **Test**
redirects every message to a configurable test recipient (default
`EMAIL_REDIRECT_TO`) and adds a "redirected while testing" banner; **Live**
sends to the real recipients. `EMAIL_ENABLED` still gates whether Outlook
sends at all. Defaults live in `email_template_service.DEFAULTS`.

## Frontend layout (`frontend/src/`)

- `main.tsx` (query client, 401 → redirect to /login), `App.tsx` (routes),
  `index.css` (Tailwind v4 + design tokens + dark variant).
  `auth/loginRedirect.ts` — deep-link preservation: unauthenticated visits
  redirect to `/login?next=<path>` (set by `ProtectedLayout` and the 401
  handler); `LoginPage` navigates to the sanitized `next` (same-app absolute
  paths only) after sign-in.
- `components/AppShell.tsx` — navy grouped sidebar (icons, active pill) +
  header (theme toggle, Sign Out).
- `components/ui/` — `Button` (primary/secondary/ghost), `Input`, `Select`,
  `PasswordInput` (eye toggle), `Card`/`StatCard`, `Badge`/`StatusBadge`,
  `QuillEditor`, `TransferList` (dual-listbox: Available | Add»/«Remove |
  Selected + ▲▼ reorder; used for approver pools and user roles, not
  checkboxes), `BrandCard` (email-look page card: navy header band + per-page
  mark — the page's own nav icon in a sky-blue rounded tile — + white title +
  sky subtitle; optional actions/subheader/footer slots; `mark` is a page key
  mapped to `NavIcons`: `dashboard`/`newRequest`/`requests`/`users`/
  `divisions`/`thresholds`/`emailTemplates`/`profile`).
- Icons: `components/NavIcons.tsx` (custom per-page sidebar line-icons — 24px
  grid, rounded joins, `currentColor`; AppShell uses these for nav, lucide
  only supplies non-nav glyphs like Sign Out) and `components/ActionIcons.tsx`
  (same-style in-page icons: Approve/Reject/Submit, row controls
  View/Edit/Delete/Download/Search/Filter/Add/Upload, workflow-status icons;
  used by `StatusBadge`, RequestDetailPage action buttons, the Wizard, and the
  Requests list — `currentColor`, so icons take their button/badge color).
  Both derive from `brand/UUS CAPEX Flow Nav Icons.html`. `components/Logo.tsx`
  (primary Capital-Cycle mark: sidebar/login); `BrandMark.tsx` (four brand
  marks, currently not wired into any page). `ThemeToggle.tsx`, `theme.ts`.
- `routes/` — `DashboardPage` (KPI StatCards + approvals table), `LoginPage`,
  `ChangePasswordPage` (full-screen forced set-your-new-password),
  `RequestsListPage` + shared `RequestsTable` (sortable column headers and a
  per-row View action; client-side comparators + `filterRequests` in
  `routes/requestsSort.ts` — status sorts in workflow order, blanks last; the
  list page adds a search box over number/division/requestor),
  `RequestDetailPage`, `ProfilePage`, and `routes/admin/` (Users, Divisions,
  Approval Thresholds, Email Templates + forms).
- `WizardPage` — 7-step request wizard (Basic Info, Description, Effect on
  Ops, Equipment, Economic, Attachments, Review), styled as an email-look
  brand card (navy header band with Logo, numbered stepper [✓ done / accent
  active], footer action bar). Two modes keyed on the route: **new**
  (`/requests/new`) starts from a blank form (division prefilled from
  `useMe().division_id`, date today) and **creates nothing** until the first
  Save Draft / Submit — those call `createDraft` then `updateDraft` and swap
  the URL to `/requests/:id/edit`; **edit** (`/requests/:id/edit`) loads the
  draft and auto-saves on Next/stepper. The wizard edits both DRAFT and
  REJECTED requests; the Review-step action calls `resubmit` when the loaded
  request is REJECTED, otherwise `submit`. The Attachments step
  uploads/removes files via the attachment API; on a new request the first
  upload lazily creates the draft (persist) then attaches.
  `routes/wizard/types.ts` maps API ↔ form (`toForm`/`toPayload`).
- Email Templates editor: `components/ui/QuillEditor` (Quill 2.x on a ref)
  with a placeholders panel, a sandboxed iframe preview, and a `TemplateTabs`
  tab bar to switch between the four templates in place — switching with
  unsaved edits prompts a discard confirm. (The list page is still the sidebar
  landing.)
- `api/` — `client.ts` (fetch wrapper; obtains CSRF from `/api/auth/csrf`,
  sends `X-CSRFToken` on mutations, `credentials: 'include'`), plus
  per-resource modules (`auth`, `requests`, `divisions`, `users`,
  `thresholds`, `profileApi`).

## Design system & brand

- **Theming:** semantic Tailwind tokens (`bg`, `surface`, `surface-2`, `border`,
  `fg`, `muted`, `sidebar`, `accent`) defined in `index.css`; dark mode is a
  class-based `@custom-variant dark` that overrides the same variables. Prefer
  these tokens over hard-coded `slate-*`. Theme persists in
  `localStorage['capex-theme']`; an inline script in `index.html` applies it
  before render to avoid a flash.
- **Page pattern:** every main page wraps its content in **one `BrandCard`**
  with the matching page `mark`. Secondary edit forms (User/Division forms,
  EmailTemplateEditor) keep plain headings.
- **Table headers:** data-table `thead` rows use the sky brand tint —
  `bg-brand-sky/25 text-brand-navy` (light) / `dark:bg-brand-sky/10
  dark:text-brand-sky` — uppercase `text-xs`. Bryan found plain `surface-2`
  too subtle and solid navy too bold; new tables should match this.
- **Brand (`brand/`, "UUS CAPEX Flow"):** `brand_asset.pdf` plus
  `UUS CAPEX Flow - Logo.dc.html` (the four logo-direction mockups). Palette
  navy `#0B2A4A`, blue `#2563EB`, sky `#93BBF5`. Logo mark = direction **1d
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
  **Finance-section fields** follow a parallel path instead: model + migration,
  `FinanceIn` schema, `workflow_service._FINANCE_FIELDS`, `request_out`,
  frontend `CapexRequestData` + the `FinanceForm`/read-only views in
  `RequestDetailPage` (and its test mocks, which build full objects).
- `index.css` hides the Edge/IE native password-reveal eye (`::-ms-reveal`) —
  `PasswordInput` provides its own toggle; without this users see two eyes.
- If `DEFAULT_PASSWORD` ever changes, update it in lockstep: the config
  constant, the literal "Welcome@1" copy in `UserForm.tsx` (new-user note) and
  `UserEditPage.tsx` (reset section), and this file.
- Deferred auth follow-ups (final review 2026-07-15, all minor): no vitest for
  `ChangePasswordPage` validation or the reset-to-default confirm flow; the
  "Sign out instead" button doesn't guard a rejected `logout()`; non-`ApiError`
  failures render nothing in `UserEditPage` reset/delete; an admin reset does
  not invalidate the target user's existing session/remember cookie.
- `docs/superpowers/specs/` holds design specs; milestone/phase plans live under
  `docs/`.

## Phase 2 — proposed enhancements (pending Finance review)

Five proposed features (budget tracking, exports/reporting, reminders,
comment threads, approved-request PDF) are documented in
**`PHASE2-PROPOSALS.md`** (repo root) — **read that file when Bryan says
"implement phase 2"** or asks about any of them. Do not build until Finance
has reviewed `CAPEX Flow - Proposed Enhancements.docx` and answered its
"Questions for Finance".
