# CLAUDE.md

Coding rules: @CODING-RULES.md

# Project: CAPRI

Internal web app for **United Uptime Services** to submit, route, approve, and
search capital-expenditure (CAPEX) requests. Product brand name: **CAPRI** —
Capital Approval, Planning, Reporting & Investment (under "United Uptime
Services"). Renamed from "CAPEX Flow" on 2026-07-30; the domain word CAPEX
deliberately stays in the code (`CapexRequest`, `capex_requests`, `CX000001`
numbering, the `capex_tracking` folder) because a request still *is* a capital
expenditure. See
`docs/superpowers/specs/2026-07-30-capri-rebrand-design.md`.

## Stack

- **backend/** — Flask API (Python 3.14), SQLAlchemy 2.0 (typed `Mapped`),
  Flask-Login session auth + CSRF (login sets a 30-day remember-me cookie so
  email deep links survive browser restarts; `REMEMBER_COOKIE_*` in config),
  Pydantic v2 request schemas, Alembic migrations. **SQLite** in dev (`backend/instance/capex_dev.db`), **Azure SQL
  Server** in prod.
  **Database URL:** `config._database_url()` takes `DATABASE_URL` if set,
  else builds `mssql+pyodbc:///?odbc_connect=…` by URL-encoding
  `AZURE_SQL_ODBC` — the raw ODBC string pasted from the Azure portal, whose
  password characters (`+ # ) !`) a plain SQLAlchemy URL would mis-parse —
  else falls back to SQLite. Both live in **`backend/.env`** (git-ignored);
  `config.py` calls `load_dotenv()` so `python seed.py` sees it too, not just
  the `flask` CLI. Azure SQL needs `pyodbc` plus the system "ODBC Driver 18
  for SQL Server".
  **`quote_plus` is applied twice on purpose** (2026-09-18): the value is
  decoded *twice* before pyodbc sees it — once when SQLAlchemy parses the URL
  query string, and again in `sqlalchemy/connectors/pyodbc.py`, which calls
  `unquote_plus()` on the already-decoded value. Encoding once (the pattern in
  SQLAlchemy's own docs) silently turns the literal `+` in the password into a
  space and the login fails with 18456 — while a bare `pyodbc.connect()` with
  the same string succeeds, which is what makes it confusing to diagnose.
  `tests/test_config.py` pins the round trip.
  The dev server `uus-capri-dev-scus-sql` is **private-endpoint-only**; as of
  **2026-09-18 it is reachable from the office network** — the hostname
  resolves through its `privatelink` CNAME to **172.16.31.204** and the app
  runs against it (schema migrated to `e7f8a9b0c1d2` and seeded). Off that
  network there is still no public A record, so comment `AZURE_SQL_ODBC` back
  out in `.env` to fall back to the local SQLite file.
- **frontend/** — React 19 + Vite 6 + TypeScript SPA. React Router 7, TanStack
  Query 5, Tailwind CSS v4, `lucide-react` icons. **Single-server:** the SPA is
  built (`vite build` → `frontend/dist`) and served by Flask itself — the app
  runs as one server on `http://localhost:5100` (Flask serves `dist` plus the
  `/api` routes; a catch-all returns `index.html` for client-side routes). The
  API client uses relative `/api`, so it's same-origin. There is no Vite dev
  proxy.

## Running the app

**Windows gotcha:** the repo path contains `&` (`D&H United Fueling Solutions`),
which breaks npm's default cmd script-shell and breaks running `npm run …`
through tools that shell out. Two consequences:
- Double-click **`Start CAPRI.cmd`** (repo root), or run **`run-app.ps1`**
  from a PowerShell prompt (`powershell -ExecutionPolicy Bypass -File
  .\run-app.ps1` if script execution is blocked). It does first-run setup (venv,
  deps, `flask db upgrade`, `python seed.py`), **builds the frontend**, starts
  the single Flask server (`flask run --port 5100`) in its own window, and opens
  the browser to `http://localhost:5100`. It launches the server from its own
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
    pip install -r requirements.txt && flask db upgrade && python seed.py && flask run --port 5100

App: http://localhost:5100 (`GET /api/health` → `{"status":"ok"}`) ·
Dev login: **admin@uniteduptime.com / ChangeMe123!**
(To iterate on the frontend, rebuild with `node ./node_modules/vite/bin/vite.js
build`; there is no live dev server.)

## Testing

- Backend: `cd backend && pytest -q` (currently 426 tests).
- Frontend: `npm test` (vitest) and `npm run build`; typecheck with `tsc`.
- Always run backend pytest + frontend typecheck after changes touching either.

## Backend layout (`backend/app/`)

- `models/__init__.py` — all SQLAlchemy models (see Data model below).
- `blueprints/` — HTTP routes, one per resource, each mounted under `/api/...`:
  `health`, `auth` (`/api/auth`, email-based login plus `set-password`),
  `users`, `divisions`, `thresholds`, `profile`, `requests`, `email_templates`
  (`/api/email-templates`, ADMIN-only), `reports` (`/api/reports`, FINANCE/ADMIN
  summary endpoint), `request_sections` (`/api/request-sections` — which wizard
  steps are hidden; **GET is open to any signed-in user** because the wizard
  needs it, PUT is ADMIN-only), `regions` (`/api/regions`, ADMIN-only GET/POST/
  PATCH; `region_out` serializes id/name/active/vp_approver_ids/names/
  division_count), `pings` (`/api/pings`, every signed-in user; see Pings).
  Routes are thin; they validate input
  with Pydantic schemas and delegate to services. A flagged
  `must_change_password` user is blocked from the rest of the API by an
  app-level `before_request` (403 `PASSWORD_CHANGE_REQUIRED`), exempting only
  `auth.set_password`/`auth.me`/`auth.csrf_token`/`auth.logout`.
- `services/` — business logic: `request_service`, `workflow_service`
  (approval routing), `auth_service`, `user_service`, `division_service`,
  `threshold_service`, `profile_service`, `attachment_service`/`storage`,
  `counter_service` (request numbers `CX000001…`), `comment_service` (adds a
  request comment; authz delegated to `request_service.get_request`, so "if you
  can see the request, you can comment on it" is one rule, not two), `notify` (writes
  `NotificationLog`, renders emails via templates; asks `settings_service`
  for the delivery mode to pick the recipient), `settings_service`
  (app-wide settings in the `AppSetting` table — the email delivery mode:
  Test redirects all mail to a test recipient, Live sends to real
  recipients; defaults to Test + `EMAIL_REDIRECT_TO`; plus
  `get/set_hidden_sections`, the hidden wizard steps as a JSON array under
  `wizard_hidden_sections`, defaulting to none), `email_template_service`
  (six editable email templates: defaults, tokens, render, three-tier reset),
  `email_frame` (brand HTML wrapper; the rounded chrome — header band 640×100,
  CTA buttons, bottom strip — is baked into `assets/*.png` because classic
  Outlook's Word engine can't round CSS corners and mangles VML on send.
  **Regenerate with `python tools/gen_email_assets.py`** from `backend/` —
  only the header carries the product name; see its docstring before using
  `--all`, which produces button pills a few px wider than the committed ones),
  `email_outlook` (Outlook COM sender; attaches referenced `cid:capri-*`
  assets), `security`, `errors` (`ServiceError(msg, status)`),
  `region_service` (CRUD for regions — `list_regions`, `create_region`,
  `update_region`; enforces unique region name),
  `export_service` (xlsx export of the requests list via openpyxl),
  `report_service` (year summary aggregates, computed Python-side),
  `pdf_service` (record PDF of one request via reportlab — see "Record PDF"
  below; `request_pdf_sections` decides the content as plain dicts and
  `render_pdf` is the only reportlab-aware part, so content rules are testable
  without parsing PDFs),
  `ping_service` (in-app messaging between users, optionally referencing a
  request — see "Pings" below).
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
  `division_l1_approvers`: the Level-1 approver pool for its requests),
  `region_id` (nullable FK to `Region`; the Division form requires picking one
  even though the column is nullable at the DB level).
- **Region** — `name` (unique), `active`, `vp_approvers` (many-to-many via
  `region_vp_approvers`: the Level-2 approver pool for every division in the
  region); `divisions` back-populates `Division.region`. Migration
  `d4e5f6a7b8c9`.
- **ApprovalThreshold** — one row per `level` (1/2/3), `max_amount` (top level
  usually null = no cap), `approvers` (many-to-many via `threshold_approvers`;
  L1 comes from the division, L3 still comes from here). Each level can have
  multiple approvers and **any one** may act. **The level-2 `approvers` column
  is now vestigial** — L2 routing reads the request's division's region's
  `vp_approvers` instead (see Roles & approval workflow below); the rows are
  kept and the threshold PUT still accepts `approver_ids` for level 2, but
  nothing reads them.
- **CapexRequest** — `number`, `status`, `requestor_id`, `assignee_id` (current
  approver), `division_id`, `request_date`; Basic-info flags (`budgeted`,
  `replacement`, `health_safety`, `revenue_generating`, `environmental`,
  `competitive_bids`, `lease_recommended`) plus `budget_amount` (the dollar
  figure that `budgeted` requires — see "Budgeted amount" below); narrative (`justification`,
  `effect_on_operations`); economic fields (`irr_after_tax`,
  `first_year_ebit`, `annual_savings`, `payback_years`, `npv_savings`) plus
  `asset_life` — an economic *column* that since 2026-08-07 is presented on
  **Basic Info** as "Useful / asset life" (wizard, detail page, record PDF;
  export column "Useful / Asset Life"), so hiding the Economic section no longer
  hides it. Not to be confused with Finance's
  `useful_life_years`/`useful_life_months`; finance
  cost breakdown (`cost_*`, asset details `asset_number`/`gl_account`/
`useful_life_years`+`useful_life_months`/`in_service_date`,
  `finance_completed`); `total_cost`,
  `required_levels`, `current_level`. Money = `Numeric(18,2)`, ratios =
  `Numeric(9,4)`.
- **EquipmentItem** — line items (`units`, `condition` NEW/USED, `type`, `make`,
  `model`, `cost`); sum drives `total_cost`.
- **Attachment**, **ApprovalAction** (audit trail: SUBMITTED/APPROVED/REJECTED/
  RESUBMITTED/FINANCE_COMPLETED, with `level`, `comment`, `acted_for_id` for
  delegated actions), **NotificationLog**, **Counter**, **AppSetting**.
- **RequestComment** — the Q&A thread (`author_id`, `body`, `created_at`).
  **Immutable**: no `updated_at`, and no edit or delete route exists. Cascades
  with the request. Carried on `request_out` as `comments`, so there is no
  separate GET.
- **EmailTemplate** — one row per email `type` (ASSIGNED/APPROVED/REJECTED/
  FINANCE_READY/FINANCE_COMPLETE/COMMENT): live `subject`/`body_html`/`enabled` plus `default_subject`/
  `default_body_html` (admin-set baseline). A row exists only once customized;
  code holds the shipped defaults (`email_template_service.DEFAULTS`).
- **Ping** / **PingRecipient** — in-app messaging between users, optionally
  referencing a request. See "Pings (in-app messaging)" below.

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
**pool** of approvers — L1 from the request's division, **L2 from the
division's region's `vp_approvers`** (not the threshold row —
`workflow_service.intended_approvers` reads `division.region.vp_approvers`),
L3 from the threshold row — each mapped through their out-of-office delegate;
**any one** eligible approver may approve (advances) or reject. The pool
appears on every member's "assigned" worklist; `assignee_id` is just a display
hint (the first current approver) — `request_service._can_view` therefore
admits **every eligible actor at the current level**, not just `assignee_id`
(before 2026-08-05 it didn't, so a second pool approver got a 403 opening a
request from their own worklist).

**Requestors cannot approve their own requests.** Every pool computation
(`workflow_service.eligible_actors`, `first_assignee`, `next_pending_level`)
takes an `exclude_id` — the requestor is filtered out both if they sit directly
in a pool and if they're another approver's out-of-office delegate. If that
leaves a level with nobody eligible, `next_pending_level` skips it and opens
(or advances into) the next non-empty level above it, so `submit`/`resubmit`
can open a request at L2 or L3 directly, and `approve()` can jump past an empty
level — the request still reaches `APPROVED` once the acting level meets or
exceeds `required_levels`, so one escalated approval can suffice. If **no**
level has an eligible approver anywhere, `_open_workflow` raises: "No eligible
approver was found at any level — requestors cannot approve their own
requests. Check the division's level-1 approvers, the region's VP list, and
the level-3 approvers." The same requestor exclusion is threaded through
`request_service` (`_can_view`, the assigned worklist, `request_out`'s
approver lists) and `notify` (assignment + comment recipients), so a requestor
never sees their own request on an approval worklist even if they'd otherwise
qualify for a pool.

An approver has a **third response**: the **comment thread** on the detail page
(`POST /api/requests/<id>/comments`). A comment changes no status, level, or
assignee — the request stays with the same people — so a question no longer
requires a rejection. Anyone who can view the request can post, at any status.
Comments are immutable and appear in the record PDF. See "Comment thread" below.

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
treated as UTC), the comment thread (`components/CommentThread.tsx`), and a
collapsed-by-default "Full request details" toggle
(`FullDetails`) exposing everything captured in the wizard. Attachment
permissions (`attachment_service._can_modify`): the requestor manages
attachments while DRAFT/REJECTED; FINANCE once APPROVED. Attach-file UI
(wizard + detail page) is a button over a hidden file input — picking a file
uploads immediately.

Each transition sends a notification email (assignment/decision/finance-ready/
record-complete/new-comment) via the local Outlook desktop app (`email_outlook`). Emails are
**editable HTML templates** — admins customize subject, body (WYSIWYG), and
enabled flag per type under **Admin → Email Templates**, with `{token}` placeholders
substituted at send time and a brand-styled locked frame. A runtime **delivery
mode** (Test/Live — toggled from the Email Templates page and editor via
`components/admin/EmailDeliveryMode.tsx`, stored in `AppSetting`, exposed at
`GET/PUT /api/email-templates/settings`) picks the recipient: **Test**
redirects every message to a configurable test recipient (default
`EMAIL_REDIRECT_TO`) and adds a "redirected while testing" banner; **Live**
sends to the real recipients. `EMAIL_ENABLED` still gates whether Outlook
sends at all. Defaults live in `email_template_service.DEFAULTS`.

## Deployment (Dev — in progress)

Tracked on Azure DevOps Boards (FinanceApps, area `Solutions\CAPRI`): PBI
**5879** (code: container-ready), **5880** (IT: Dev environment), **5881**
(Entra SSO). Target is APEX's pattern — Azure Container Apps, settings as env
vars, secrets from Key Vault, owned by IT's infra repo.

- **`Dockerfile`** (repo root) + **`.dockerignore`** +
  **`backend/gunicorn.conf.py`** + **`pipelines/azure-pipelines-dev.yml`**
  (added 2026-09-25). **No Docker locally — IT forbids it.** The image is built
  in Azure by `az acr build`; the first real test of the Dockerfile is a
  pipeline run, so keep it close to APEX's.
- Stages: `frontend` (vitest + `npm run build`, i.e. tsc + vite) → `base`
  (Python 3.14 + ODBC Driver 18 + requirements) → `test` (pytest; the final
  stage copies its marker so a failing test fails the build) → `final`.
  Layout mirrors the repo (`/app/backend`, `/app/frontend/dist`) because
  `create_app()` finds the SPA relative to the repo root.
- The container runs `flask db upgrade` then gunicorn (2 gthread workers —
  safe because all auth state is in the signed session cookie).
- `.dockerignore` must keep excluding `**/.env` — `config.py`'s
  `load_dotenv()` would bake the Azure SQL password into the image.
- Pipeline triggers on the Azure **`dev`** branch. Every resource name in it
  (`ca-capri-dev`, `uus-capri-dev-scus-rg`, `uuscapridevscusacr`, the pool and
  `uus-dev-sc`) is **proposed by analogy with APEX, not confirmed by IT**.
- **`APP_BASE_URL` is the one switch for which config runs** (ADO 5883,
  `config.config_from_env()`, read at call time): unset/localhost →
  `DevConfig` (unchanged local behaviour); anything else → `ProdConfig`
  (secure cookies, **no SQLite fallback** — no DB URL means Flask-SQLAlchemy
  refuses to start — and `EMAIL_ENABLED` default-off). There is deliberately no
  separate environment flag. `create_app` then refuses to start a non-local
  `APP_BASE_URL` that still has the repo's `INSECURE_DEV_SECRET` (or none), or
  that isn't `https://`. No ProxyFix: nothing builds URLs from the request
  scheme (redirects are relative; SSO's redirect URI is configured).
- **Seeding vs. a real admin** (ADO 5885): `python seed.py` refuses any
  non-SQLite database unless given `--allow-non-sqlite`, because its admin
  password (`ChangeMe123!`) is public — so with `AZURE_SQL_ODBC` in `.env`
  it refuses on a developer PC too. On a deployed database use
  **`python create_admin.py <email> "<name>"`** (prompts twice; ≥12 chars;
  ADMIN role only; refuses an existing email). The Dev Azure SQL database was
  seeded on 2026-09-18, so its `admin@uniteduptime.com` must be deactivated or
  re-passworded at first deploy (ADO 5896).
- **Still not deployable:** email is Outlook-only until the SendGrid backend
  (ADO 5884).

## Entra ID SSO

Spec: `docs/superpowers/specs/2026-09-21-capri-entra-sso-design.md`. House
recipe: `docs/entra-sso-implementation-guide.md`. Support runbook:
`docs/sso-support-runbook.md`. IT request:
`docs/it-requests/2026-09-21-capri-entra-sso.md`. Built 2026-09-21 as **Step 0**
— the code ships with the flag **unset**, so the SSO routes 404 and nothing
changes for users until an Entra app registration exists.

- **One switch: `sso_config() is not None`.** SSO is on only when
  `CAPRI_ENABLE_SSO=1` **and** all five `CAPRI_SSO_*` values are present
  (tenant, client id, client secret, at least one group object ID, redirect
  URI). Not-None also means SSO is the **only** way in: `POST /api/auth/login`
  returns 403 as its first line, and the login screen renders only the
  Microsoft button. Two independent flags drift apart and leave a door open, so
  there is only ever one condition. An incomplete config fails **open** (SSO
  off, password login works) and logs a startup `WARNING` — a typo must not lock
  everyone out of a working app.
- All six vars live in `backend/.env` (git-ignored; the repo mirrors to
  GitHub). `CAPRI_SSO_ALLOWED_GROUPS` takes **object IDs, not display names** —
  a display name fails every sign-in at gate 2 as `not_in_group`.
- **`app/services/sso_service.py` is the only module importing `msal`**; routes
  stay thin in `blueprints/auth.py` (`GET /api/auth/config`,
  `GET /api/auth/sso/login`, `GET /api/auth/sso/callback`, both 404 when off).
  `_client(cfg)` is the single seam the tests fake.
- **Four gates, and the order is load-bearing** — each code names a different
  fixer, so running them out of order hands an IT problem to an app admin:
  `no_groups_claim` (claim absent or not a list — *not* "member of nothing";
  Entra drops it for users in many groups) → `not_in_group` → `unknown_user` /
  `inactive_user` (no auto-provisioning, no group→role mapping; roles stay in
  the admin screen) → `identity_mismatch` (`users.entra_oid`, pinned on first
  sign-in). Plus `auth_failed` from the token exchange. Codes are a fixed
  vocabulary: no exception text, claim value or email may reach the browser.
- **`sso_config()` reads `os.environ` at call time and must NOT become a
  `Config` class attribute.** `config.py` assigns at import, which would make
  the config untestable and let a developer's `.env` 403 the whole suite — the
  `_no_ambient_sso` autouse fixture in `tests/conftest.py` is the guard, and
  removing it makes failures move around as tests are added.
- **Failures redirect to `/login?sso_error=…`, not `/`** (the guide's target):
  `/` is inside `ProtectedLayout`, which would bounce to `/login?next=/` and
  discard the code. Never a JSON body — the browser is mid-navigation.
- **`response_mode` stays query/GET.** `SESSION_COOKIE_SAMESITE="Lax"` does not
  send the cookie on a cross-site POST, so a `form_post` callback would arrive
  with no session and break every sign-in while looking like an Entra
  misconfiguration.
- **SSO sessions use `remember=False`** (the password path keeps
  `remember=True` and its 30-day cookie) so revoking Entra access takes effect
  promptly; deep links still arrive via `?next=`, validated by `safeNext`
  client-side and `safe_next_path` server-side.
- **`must_change_password` is skipped, not cleared, for SSO sessions** — in
  `_require_password_change` (`app/__init__.py`) and in `ProtectedLayout`, which
  reads the new `auth_method` field on `/api/auth/me`. There is no password to
  change, but the flag still applies if `CAPRI_ENABLE_SSO` goes back to 0. The
  password endpoints, `ChangePasswordPage` and the admin reset all stay —
  they're what makes `CAPRI_ENABLE_SSO=0` a real recovery lever, and there is
  deliberately **no in-app break-glass password**.
- **Migrations:** `c9d0e1f2a3b4` adds `users.entra_oid` (nullable, **not**
  unique). `b8c9d0e1f2a3` first replaces `users.reset_token`'s plain UNIQUE
  constraint with a **filtered** unique index on SQL Server — a nullable-unique
  column allows exactly one NULL there, which capped the table at one user on
  Azure SQL. Don't reintroduce a nullable-unique column.

## Frontend layout (`frontend/src/`)

- `main.tsx` (query client, 401 → redirect to /login), `App.tsx` (routes),
  `index.css` (Tailwind v4 + design tokens + dark variant).
  `auth/loginRedirect.ts` — deep-link preservation: unauthenticated visits
  redirect to `/login?next=<path>` (set by `ProtectedLayout` and the 401
  handler); `LoginPage` navigates to the sanitized `next` (same-app absolute
  paths only) after sign-in. `openRequests.ts` — the open-request tab store,
  per-user `localStorage`; see "Open-request tabs" below.
- `components/AppShell.tsx` — navy grouped sidebar (icons, active pill) +
  header (theme toggle, `PingBell`, Sign Out), with `RequestTabs` (the
  open-request tab strip) mounted between the header and main content.
  `PingBell`/`PingPanel`/
  `PingCard`/`PingDetail`/`PingModal` are the in-app messaging components —
  see "Pings (in-app messaging)" below.
- `components/ui/` — `Button` (primary/secondary/ghost; `size` prop `'md' |
  'sm'`), `Input`, `Select`,
  `PasswordInput` (eye toggle), `Card`/`StatCard`, `Badge`/`StatusBadge`,
  `QuillEditor`, `TransferList` (dual-listbox: Available | Add»/«Remove |
  Selected + ▲▼ reorder; used for approver pools and user roles, not
  checkboxes), `BrandCard` (email-look page card: navy header band + per-page
  mark — the page's own nav icon in a sky-blue rounded tile — + white title +
  sky subtitle; optional actions/subheader/footer slots; `mark` is a page key
  mapped to `NavIcons`: `dashboard`/`newRequest`/`requests`/`users`/
  `divisions`/`thresholds`/`emailTemplates`/`profile`/`reports`/`regions`).
- Icons: `components/NavIcons.tsx` (custom per-page sidebar line-icons — 24px
  grid, rounded joins, `currentColor`; AppShell uses these for nav, lucide
  only supplies non-nav glyphs like Sign Out) and `components/ActionIcons.tsx`
  (same-style in-page icons: Approve/Reject/Submit, row controls
  View/Edit/Delete/Download/Search/Filter/Add/Upload, workflow-status icons;
  used by `StatusBadge`, RequestDetailPage action buttons, the Wizard, and the
  Requests list — `currentColor`, so icons take their button/badge color).
  Both derive from `brand/project/UUS CAPEX Flow - Nav Icons.dc.html`. `components/Logo.tsx`
  (primary Capital-Cycle mark: sidebar/login); `BrandMark.tsx` (four brand
  marks, currently not wired into any page). `ThemeToggle.tsx`, `theme.ts`.
- `routes/` — `DashboardPage` (KPI StatCards + approvals table), `LoginPage`,
  `ChangePasswordPage` (full-screen forced set-your-new-password),
  `RequestsListPage` + shared `RequestsTable` (sortable column headers and a
  per-row View action; client-side comparators + `filterRequests` in
  `routes/requestsSort.ts` — status sorts in workflow order, blanks last; the
  list page adds a search box over number/division/requestor, an
  Export-to-Excel button that downloads the current scope/status/search as
  an xlsx, and an ADMIN/FINANCE-only "All" scope tab),
  `RequestDetailPage`, `ProfilePage`, `ReportsPage` (`/reports`, FINANCE/ADMIN
  only: year picker, spend-by-division/month/status tables with inline CSS
  bars, cycle time), `MessagesPage` (`/messages` — see "Pings (in-app
  messaging)" below), and `routes/admin/` (Users, Divisions, Regions,
  Approval Thresholds, Request Sections, Email Templates + forms). Regions
  (`RegionsPage`/`RegionNewPage`/`RegionEditPage`/`RegionForm`, `api/regions.ts`,
  nav item above Divisions, ADMIN-only) manage a region's name/active flag and
  VP-approver pool via `TransferList`; `DivisionForm` requires picking a Region
  (inactive regions are hidden from the picker unless currently assigned) and
  `DivisionsPage` shows a Region column; the Approval Thresholds page's L2 card
  shows a pointer note instead of a `TransferList` since that pool is no longer
  read (see the vestigial-column note above). The Users/Divisions/Regions list
  tables are client-side sortable and filterable: shared pieces are
  `components/ui/SortHeader` (clickable th + chevrons + `aria-sort`, extracted
  from the Requests list's pattern) and `routes/admin/tableSort.ts`
  (`sortRows` — natural string order so "2" < "10", true-before-false booleans,
  blanks always last); each page has a search box, and Divisions adds a Region
  dropdown (with a "No region" choice) and an Active filter.
- `WizardPage` — 7-step request wizard (Basic Info, Description, Effect on
  Ops, Asset Details, Economic, Attachments, Review), styled as an email-look
  brand card (navy header band with Logo, a step-card stepper, footer action
  bar). The stepper (`routes/wizard/Stepper.tsx`, ported 2026-09-14 from
  SCORE's) is a row of equal-width cards, each with a badge + label + one-line
  `hint`; badge colours track progress the way SCORE's do — **green check for
  every step before the current one, accent blue for the current step, grey
  number for steps not yet reached** ("done" is positional, not tracked per
  field). Because seven cards need room, the wizard card is `max-w-5xl` where
  the other pages are `max-w-3xl`. **Steps are a keyed registry**
  (`routes/wizard/sections.ts`, each with its `hint`), not positional indexes —
  add a step there, and see "Hideable wizard sections" below. Two modes keyed on the route: **new**
  (`/requests/new`) starts from a blank form (division prefilled from
  `useMe().division_id`, date today) and **creates nothing** until the first
  Save Draft / Submit — those call `createDraft` then `updateDraft` and swap
  the URL to `/requests/:id/edit`; **edit** (`/requests/:id/edit`) loads the
  draft and auto-saves on Next/stepper. The wizard edits both DRAFT and
  REJECTED requests; the Review-step action calls `resubmit` when the loaded
  request is REJECTED, otherwise `submit`. The Attachments step
  uploads/removes files via the attachment API; on a new request the first
  upload lazily creates the draft (persist) then attaches.
  `routes/wizard/types.ts` maps API ↔ form (`toForm`/`toPayload`);
  `routes/wizard/validate.ts` holds the step-gate predicates
  (`budgetAmountError`) that `goToStep` checks before advancing.
- Email Templates editor: `components/ui/QuillEditor` (Quill 2.x on a ref)
  with a placeholders panel, a sandboxed iframe preview, and a `TemplateTabs`
  tab bar to switch between the four templates in place — switching with
  unsaved edits prompts a discard confirm. (The list page is still the sidebar
  landing.)
- `api/` — `client.ts` (fetch wrapper; obtains CSRF from `/api/auth/csrf`,
  sends `X-CSRFToken` on mutations, `credentials: 'include'`), plus
  per-resource modules (`auth`, `requests`, `divisions`, `users`,
  `thresholds`, `profileApi`, `requestSections`). `routes/formatDate.ts` holds
  `formatActionDate`, shared by the detail page and the comment thread.

## Record PDF & the finance-complete email

When Finance **first** completes the cost breakdown, the requestor gets a final
"record copy" email with a PDF of the whole request attached (spec:
`docs/superpowers/specs/2026-07-28-finance-complete-record-pdf-design.md`).

- **Trigger:** in the `POST /api/requests/<id>/finance` route (notifications
  fire from blueprints, never services). First completion is detected by
  counting `FINANCE_COMPLETED` actions on the saved request — exactly one means
  this save was the first, so **re-saves send nothing** and no signature or
  extra state was needed.
- **Manual resend:** `POST /api/requests/<id>/resend-record`, FINANCE/ADMIN
  only, 400 unless `finance_completed`. Button sits next to Download PDF.
- **Download:** `GET /api/requests/<id>/pdf` at any status; authz is just
  `request_service.get_request`, so it inherits the detail page's visibility
  rule. Frontend uses `requestPdfUrl(id)` in a plain `<a href>`.
- **Fifth email template `FINANCE_COMPLETE`** ("Record complete"). It reuses
  the existing `btn-approved` PNG because that button already reads "View the
  request" — **adding an email type needs no new baked artwork unless you want
  a new CTA label** (buttons are PNGs; see the email gotchas above).
- **Attachments:** `email_outlook.send(..., attachments=[(filename, bytes)])`
  writes each to a temp file (Outlook COM attaches from a path only) and
  cleans up after `Send()`. `notify._emit`/`_send_template` pass it through.
  **Any test that spies on `email_outlook.send` must accept `attachments=`.**
- The PDF omits admin-hidden wizard sections and omits the finance breakdown
  until `finance_completed`. Ratio columns (`Numeric(9,4)`) print via
  `money_str`, so payback shows `3`, not `3.0000`. A **Comments** table follows
  Approval history (By / Date / Comment), so the audit copy carries the Q&A
  that led to the decision.
- Nothing is stored: PDFs are generated per request.

## Comment thread

Spec: `docs/superpowers/specs/2026-08-05-request-comments-design.md`.
Built 2026-08-05 — it is Phase 2 proposal #4.

- **Pure side conversation.** `POST /api/requests/<id>/comments` writes a
  `RequestComment` and nothing else: no status, level, or assignee changes, and
  no `ApprovalAction` row. That is the whole point — an approver can ask a
  question without rejecting.
- **Who can post:** anyone who can view the request, at any status (DRAFT
  through APPROVED). Authz is `request_service.get_request` inside
  `comment_service.add_comment`, so it is literally the same rule as viewing.
- **Response:** the route returns the full `request_out(req)`, so the detail
  page refreshes from one round trip (same shape as the attachment routes).
  There is no GET — `request_out` carries `comments`.
- **Validation:** `CommentIn` (1–4000 chars, whitespace-stripped) via
  `StringConstraints`, a **type** constraint rather than a raising validator —
  see the ValidationError→500 gotcha below.
- **Sixth email template `COMMENT`** ("New comment"), tokens `{author}` and
  `{comment}`; reuses the `btn-approved` PNG. `notify.notify_comment` mails the
  *other side*, never the author: the requestor's comment goes to whoever holds
  the request (the level's approver pool while pending, all active FINANCE
  users once APPROVED, nobody on a DRAFT/REJECTED); anyone else's comment goes
  to the requestor.
- **UI:** `components/CommentThread.tsx`, rendered after the approval history.
  Like Attachments, it ignores the hidden-wizard-sections config — it is not a
  wizard step.
- **Immutable on purpose.** There is no edit or delete route; don't add one
  without deciding what that does to the audit copy.

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
- **Only recipients can Mark done.** The sender is not on the roster, so an
  answered conversation they started stays under Open in their inbox until a
  recipient ticks it (spec §3.3 + §7.1, kept as SCORE shipped it). Whether the
  sender may close their own conversation is an open product question — see
  spec §12.

## Open-request tabs

Spec: `docs/superpowers/specs/2026-09-09-open-request-tabs-design.md`. Ported from
SCORE's bid tab strip; built 2026-09-09. **Frontend only** — no backend change.

- **A tab is a pointer plus a label snapshot** in `localStorage`, keyed per user
  (`capri_open_requests:<userId>`): `{id, number, title, mode, step, seq}`.
  Store: `frontend/src/openRequests.ts` (`touchOpenRequest`, `setOpenRequestStep`,
  `closeOpenRequest`, `useOpenRequests`, `MAX_OPEN_REQUESTS = 8`). On-screen order
  is insertion order; `seq` only picks the least-recently-opened tab to evict.
- **The active tab is read from the URL** (`/requests/:id` or `/requests/:id/edit`;
  `/requests/new` never matches). `RequestTabs` renders nothing when no request is
  open. A tab remembers `mode` (`view`/`edit`) and opens that page on click.
- **Both request pages call `touchOpenRequest` when their request loads** — that
  one hook point covers the list, dashboard, email deep links and the new-request
  redirect. Both have a "Request unavailable → Close this tab" branch for a stored
  tab whose request is gone.
- **The wizard's step lives on the tab**, not in `useState`: React Router keeps
  `WizardPage` mounted when only `:id` changes, so local state carried request A's
  step onto request B. A brand-new request keeps a local step until its first save
  redirects to `/requests/:id/edit`, which seeds the new tab from `location.state`.
- **A tab click is a navigation:** unsaved edits on the current wizard step are
  discarded without a prompt (the wizard only auto-saves on Next/stepper).
  Matches SCORE; deliberate.
- **Any action that destroys a request must call `closeOpenRequest` on success**
  — `RequestDetailPage`'s Delete draft does; the list page has no delete action.
- Tests need `frontend/src/test-setup.ts` (vitest `setupFiles`): Node ≥ 22 ships an
  inert `globalThis.localStorage` that jsdom does not replace, so the shim installs
  an in-memory `Storage`. Any test touching the store clears it in `beforeEach`.
- No confirm on close (nothing is unsaved), no reorder/pin/close-all, no server-side
  persistence, no status badge on the tab, no nav change.

## Budgeted amount

Spec: `docs/superpowers/specs/2026-08-06-budgeted-amount-design.md`.
Built 2026-08-06.

- Checking **Budgeted** in the wizard's Basic Info step reveals a **Budget
  amount** field (hidden otherwise) that must be filled in before the step can
  be left.
- **The column is derived from the flag.** `toPayload` sends
  `budgeted ? AMOUNT(budget_amount) : null`, and `update_draft`'s `setattr` loop
  writes the null through, so unchecking clears the stored amount. Anything
  reading `budget_amount` can trust it without also checking `budgeted`.
  Unchecking and re-checking therefore means retyping the number.
- **The gate is client-side, on Next and the stepper only** —
  `budgetAmountError` in `routes/wizard/validate.ts`, called from
  `WizardPage.goToStep`. **Save Draft deliberately skips it** so a
  half-finished request is never lost (the wizard holds the form in memory until
  a save). Back needs no guard: Basic Info is always step 0.
- **Server-side backstop** in `workflow_service._open_workflow`, so submit *and*
  resubmit reject a budgeted request with no amount (or 0). The wizard can't
  reach Review without passing the gate, but a REJECTED resubmit or a direct API
  call can.
- The amount accepts `$` and commas; `AMOUNT` in `routes/wizard/types.ts` strips
  them, because Pydantic's `Decimal` won't parse `$50,000`. Read-only echoes in
  `FullDetails`, the record PDF's Basic info section, and a `Budget Amount`
  export column all appear only when `budgeted`.

## Hideable wizard sections

**Admin → Request Sections** (`/admin/request-sections`, ADMIN-only) lets an
admin hide five of the seven wizard steps — `description`, `effect_on_ops`,
`asset_details`, `economic`, `attachments`. **Basic Info and Review are always
visible** (Basic Info carries the Division that drives L1 routing; Review
carries Submit) and the API rejects them as hideable keys.

- Single source of truth: `routes/wizard/sections.ts` — `ALL_SECTIONS`,
  `visibleSections(hidden)`, `isSectionVisible(key, hidden)`, `clampStep`.
  Step numbers are the 1-based position in the **visible** list, so hiding one
  renumbers the rest with no arithmetic anywhere else.
- Consumers all read the `['request-sections']` query: `WizardPage` (stepper +
  bodies + Review summary lines), `RequestDetailPage` (the `FullDetails`
  Justification / Effect / Economic blocks and the Asset details table), and
  the admin page. **The detail page's Attachments section deliberately ignores
  the config** — FINANCE needs it after approval.
- **Display config, not a security boundary.** The PATCH route still accepts a
  hidden section's fields, so hiding never deletes or freezes existing data;
  re-showing a section brings its values back.
- Hiding Asset Details means no line items → `total_cost` 0 → every request
  routes at Level 1. The admin page warns about this on that row.

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
- **Brand (`brand/project/`, "UUS CAPRI"):** a Claude Design handoff bundle —
  `UUS CAPEX Flow - Logo.dc.html` (the four logo-direction mockups; the
  filenames still say CAPEX Flow, the contents say CAPRI) and
  `UUS CAPEX Flow - Nav Icons.dc.html`. **Read these as source, not in a
  browser** — the canvas runtime (`support.js`), the print export, the 484 KB
  `Nav Icons.html` and the canvas thumbnails were removed 2026-09-15, so the
  `.dc.html` files no longer render interactively; everything that matters
  (dimensions, colors, geometry) is in their markup, and the shipped output
  lives in `NavIcons.tsx`/`ActionIcons.tsx`/`Logo.tsx`.
  Palette navy `#0B2A4A`, blue `#2563EB`, sky `#93BBF5`. Logo mark =
  direction **1d "Capital Cycle"**, geometry on a 100-unit viewBox
  (`components/Logo.tsx` + `public/favicon.svg`) — the chevron points **up**;
  an earlier 48-unit version had it pointing left, which is why the mark
  changed appearance at the rename. Wordmark is two-tone `CAP` + `RI`
  (`components/Wordmark.tsx`; accent = `brand-accent` `#5B9BFF` on navy,
  `brand-blue` on light). **The sidebar and login card use the brand's dark
  lockup** — `components/Lockup.tsx`: mark + `CAPRI` wordmark (the
  letterspaced `UUS` was dropped 2026-08-18), left-justified, with a navy
  rounded `panel` on the light login card. Both screens spell out the acronym
  — "Capital Approval, Planning, Reporting & Investment" — via Lockup's
  `subtitle` prop, which renders in a sky-tinted column **under the wordmark,
  beside the mark** (2026-08-19: it used to be a separate full-width line
  below the lockup, which wrapped under the symbol; mark sizes went up to
  72 sidebar / 72 login to balance the taller text block; the sidebar went 56→72 on 2026-09-09 because the subtitle wraps to three lines at common widths). Bryan
  picked this over the earlier "United Uptime Services / CAPRI" stack
  (`brand/capri-dark-lockup.png` is the artwork he chose). The **email band
  keeps** the full company name + tagline and the duller `#93BBF5` mark, which
  he signed off as-is — hence `Logo`'s `accent` prop, which the
  email-template editor sets to `#93BBF5` so its replica still matches the
  sent PNG. The brand sheet sets Archivo 800 for the wordmark, but the app
  keeps its system font stack and Arial Bold in the email PNG — no webfont. No IBM
  Plex typeface (default system font). The look-and-feel targets the "ARIA"
  reference dashboard.

## Conventions & gotchas

- **After each significant change, update the docs and commit.** Keep this
  CLAUDE.md (and any relevant `docs/superpowers/specs/`) in sync with the code,
  then make a focused git commit with a clear message describing what changed
  and how it was verified. Don't batch several unrelated changes into one commit.
- **Two git remotes, different targets (since 2026-09-18).** `origin` is GitHub
  (`bnfarrellUUS/capex_workflow`) and `azure` is Azure DevOps
  (`dh-united/FinanceApps/_git/capri`, mirrored 2026-09-15). Work on local
  `main`. After committing, push it to GitHub's `main` and to Azure's **`dev`**:

      git push origin main && git push azure main:dev

  **Never push to `azure main`** — Bryan promotes `dev` → `main` on Azure
  himself, so that remote's `main` is expected to lag until he does. GitHub's
  `main` and local `main` stay identical; if one gets ahead, fast-forward
  rather than forcing (the only force push so far was the initial mirror,
  which replaced Azure's auto-generated placeholder README commit).
- Keep routes thin; put logic in `services/`. Raise `ServiceError(msg, status)`
  for handled API errors.
- New editable request fields must be added in **all** of: model, `request_out`
  serializer, `RequestDraft` schema, frontend `CapexRequestData`/`RequestForm`,
  and `toForm`/`toPayload` — missing the Pydantic schema silently drops the field.
  **Finance-section fields** follow a parallel path instead: model + migration,
  `FinanceIn` schema, `workflow_service._FINANCE_FIELDS`, `request_out`,
  frontend `CapexRequestData` + the `FinanceForm`/read-only views in
  `RequestDetailPage` (and its test mocks, which build full objects).
- **Known bug (pre-existing, unfixed):** the app-wide `ValidationError` handler
  in `app/__init__.py` calls `err.errors()`, which embeds the raw `ValueError`
  in the error's `ctx` — `jsonify` can't serialize it, so any schema whose
  `field_validator` *raises* returns a 500 instead of 400. This already affects
  `PUT /api/email-templates/settings` with a malformed `test_recipient`. Until
  it's fixed (`err.errors(include_context=False)` or `json.loads(err.json())`),
  express new constraints as types — `Literal`, bounds — rather than raising
  validators; see `schemas/request_sections.py`.
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
- **Removed 2026-09-15 — older specs still link to them.** These were reference
  material, never code: `BID-APP-STARTER-GUIDE.md` (blueprint meant to be copied
  into the Bid Flow repo), `email-rounded-corners-guide.md` (the Outlook
  rounded-corner recipe — its live descendant is
  `backend/tools/gen_email_assets.py` plus the email gotchas above), and
  `2026-07-08-capex-phase1-foundation-plan.md` (the abandoned Next.js/Prisma
  stack; its companion spec was deleted at the Flask rebuild). Pointers to them
  in `2026-07-28-bid-app-email-system-design.md`,
  `2026-07-30-capri-rebrand-design.md` and
  `2026-09-09-open-request-tabs-design.md` are dead — the specs are kept as
  historical records and were not rewritten. `2026-07-08-capex-tracking-design.md`
  **stays**: it is still the master requirements doc.

## Phase 2 — proposed enhancements (pending Finance review)

Five proposed features (budget tracking, exports/reporting, reminders,
comment threads, approved-request PDF) are documented in
**`PHASE2-PROPOSALS.md`** (repo root) — **read that file when Bryan says
"implement phase 2"** or asks about any of them. Do not build until Finance
has reviewed `CAPEX Flow - Proposed Enhancements.docx` (filename predates the
CAPRI rename) and answered its
"Questions for Finance".
