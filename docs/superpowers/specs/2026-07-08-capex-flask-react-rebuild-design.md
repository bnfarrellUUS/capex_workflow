# CAPEX App — Flask + React Rebuild Design

**Date:** 2026-07-08
**Status:** Approved by Bryan Farrell
**Supersedes:** the Next.js Phase 2 spec (removed). Requirements source of truth remains `2026-07-08-capex-tracking-design.md` (master design).
**Decision:** Migrate the entire application from Next.js/TypeScript/Prisma to a **Flask (Python) backend + React (TypeScript) SPA**, driven by a Python-first team. Reuse the existing database schema and brand color palette; rebuild all logic and UI. The existing `capex-app` (Next.js) is **removed** during the rebuild.

## 1. Scope

Rebuild the **whole app in one plan**:

- **Phase 1 parity:** username/password auth with lockout, self/admin password reset, profile + delegate, and admin management of users, divisions, and approval thresholds (per-division L1 approver; company-wide L2/L3).
- **Phase 2 request module:** 6-step request wizard, drafts, attachments, submit → threshold routing, approve/reject with comment, resubmit rejected, delegation, Finance cost-section completion, request detail page, and a My Requests list with filters.

Reuse: the **DB schema** (translated to SQLAlchemy) and the **brand colors**. Rebuild everything else.

### Out of scope (later phases)
Dashboard approval-queue widgets, the daily stale-approval reminder job, real M365 SMTP credentials, and PDF/Excel export. An email adapter with a dev logger stands in for SMTP until credentials exist.

### Styling
**Color only.** Brand palette navy `#0B2A4A`, blue `#2E6DF0`, sky `#8FB2FF`. No logo mark, no custom favicon, no special typeface (default system sans). Standing user preference.

## 2. Project structure

Monorepo, two apps; the old Next.js app is deleted once the schema and brand tokens are ported over.

```
capex_tracking/
  backend/
    app/
      __init__.py            # app factory
      config.py              # env-based config (dev/test/prod)
      extensions.py          # db, login_manager, csrf instances
      models/                # SQLAlchemy models
      schemas/               # Pydantic request/response schemas
      services/              # business logic (auth, users, divisions, thresholds, requests, workflow, attachments, notify, storage)
      blueprints/            # HTTP layer: auth, users, divisions, thresholds, requests, attachments
    migrations/              # Alembic (Flask-Migrate)
    tests/                   # pytest
    seed.py                  # dev seed (admin user, sample divisions/thresholds)
    pyproject.toml / requirements.txt
  frontend/
    src/
      main.tsx, App.tsx
      api/                   # typed fetch client (credentials + CSRF), query hooks
      routes/                # pages
      components/            # UI primitives + shared components
      lib/                   # zod schemas, helpers
    index.html, vite.config.ts, tailwind config
  docs/ ...                  # design + specs (unchanged)
```
`capex-app/` (Next.js) is removed during the rebuild.

## 3. Backend architecture (Flask)

- **App factory + blueprints**, one blueprint per domain (`auth`, `users`, `divisions`, `thresholds`, `requests`, `attachments`).
- **Layered:** blueprint (HTTP parse/authorize/serialize) → service (business logic, returns typed results) → models (SQLAlchemy). Services never touch `request`/`session` directly.
- **Service result convention:** services return either a value or raise a typed `ServiceError(message, http_status)`; blueprints translate to JSON error bodies. (Analogous to the current `ServiceResult`.)
- **Config** via env vars + `python-dotenv`; separate `DevConfig`/`TestConfig`/`ProdConfig`.

## 4. Data layer

- **SQLAlchemy 2.x** (typed, `Mapped[...]`) + Flask-SQLAlchemy. **Alembic** migrations via Flask-Migrate.
- **Databases:** SQLite (dev), **Azure SQL Server** (test/prod) via `mssql+pyodbc`. Avoid provider-specific features so both behave identically. Roles stored as a JSON string; statuses/actions stored as validated strings (not DB enums) for cross-DB parity — same approach as today.
- **Models** (translated 1:1 from the current Prisma schema, same tables/columns):
  - **User** — id, username (unique, lowercased), email (unique, lowercased), name, password_hash, roles (JSON string), active, division_id (FK), delegate_id (self-FK), failed_logins, locked_until, reset_token, reset_token_expiry, timestamps.
  - **Division** — id, number (unique), name, active, l1_approver_id (FK User).
  - **ApprovalThreshold** — id, level (1/2/3, unique), max_amount (nullable = top level), approver_id (FK User; used for L2/L3, company-wide).
  - **CapexRequest** — id, number (`CX######`, unique), status, requestor_id, assignee_id, division_id, request_date; basic-info flags (budgeted, replacement, health_safety, revenue_generating, environmental, competitive_bids, lease_recommended) + description; narrative (justification, effect_on_operations); economic (asset_life, irr_after_tax, first_year_ebit, annual_savings, payback_years, npv_savings); finance (cost_autos_trucks, cost_machinery, cost_improvements, cost_furniture, cost_permits, cost_misc, finance_completed); total_cost, required_levels, current_level; timestamps.
  - **EquipmentItem** — id, request_id (FK, cascade), units, condition (NEW/USED), type, make, model, cost.
  - **Attachment** — id, request_id (FK, cascade), filename, storage_path, content_type, size, uploaded_by_id, created_at.
  - **ApprovalAction** — id, request_id (FK, cascade), actor_id, acted_for_id (delegation), action (SUBMITTED/APPROVED/REJECTED/RESUBMITTED/FINANCE_COMPLETED), level, comment, created_at. Append-only.
  - **NotificationLog** — id, request_id (FK, nullable), recipient, type (ASSIGNED/DECIDED/FINANCE_READY/REMINDER), sent_at.
  - **Counter** — name (PK), value. **AppSetting** — key (PK), value.
- Money fields use `Numeric`/`Decimal`. A fresh seed script recreates the dev admin user + sample divisions/thresholds (the current `dev.db` is not reused across ORMs).

## 5. Auth & security

- **Flask-Login** server-side sessions. Cookies **httpOnly + secure + sameSite=Lax**. **CSRF protection**: `GET /api/auth/csrf` issues a token; the SPA sends it on all mutating requests; Flask validates (Flask-WTF CSRF or an equivalent double-submit).
- **bcrypt** password hashing (`passlib`/`bcrypt`). Login **rate limiting + lockout** using `failed_logins`/`locked_until`; reset both on success. Case-insensitive username/email. Constant-time compare + dummy hash on unknown user to avoid enumeration timing (a Phase-1 carry-over item, folded in here).
- Every endpoint enforces **role + ownership** server-side. Attachments are served only through an access-checked route.

## 6. API design (REST, JSON, session-cookie auth)

```
POST   /api/auth/login                 -> sets session cookie
POST   /api/auth/logout
GET    /api/auth/me                    -> current user + roles
GET    /api/auth/csrf                  -> csrf token
POST   /api/auth/password              -> self change password
POST   /api/auth/reset-request | reset -> forgot-password flow
GET    /api/profile ; PATCH /api/profile        -> delegate, etc.

GET/POST        /api/users ; GET/PATCH /api/users/:id ; POST /api/users/:id/reset-password   (admin)
GET/POST        /api/divisions ; PATCH /api/divisions/:id                                     (admin)
GET/PUT         /api/thresholds                                                               (admin)

GET             /api/requests?status=&division=&from=&to=      -> viewer's list (all for Finance/Admin)
POST            /api/requests                                  -> create draft (assigns CX######)
GET             /api/requests/:id                              -> detail
PATCH           /api/requests/:id                              -> save draft section (owner, DRAFT/REJECTED)
POST            /api/requests/:id/submit | approve | reject | resubmit | finance
GET/POST        /api/requests/:id/attachments
GET/DELETE      /api/requests/:id/attachments/:attId           -> access-checked download / delete
```

## 7. Validation

- **Pydantic v2** for request bodies and response serialization. **Draft-lenient** vs **submit-strict** schema variants for `CapexRequest`. ORM → JSON via Pydantic response models (`from_attributes`).
- Frontend mirrors the same rules in **Zod** for immediate form feedback; the server remains the source of truth.

## 8. Frontend architecture (React SPA)

- **Vite + React + TypeScript**.
- **React Router** routes: `/login`, `/` (dashboard placeholder as today), `/requests`, `/requests/new`, `/requests/:id`, `/requests/:id/edit`, `/admin/users`, `/admin/users/new`, `/admin/users/:id`, `/admin/divisions`, `/admin/thresholds`, `/profile`. A route guard redirects unauthenticated users to `/login` (checks `/api/auth/me`).
- **TanStack Query** for server state over a small typed **API client** (`fetch` wrapper: `credentials: 'include'`, injects CSRF token, throws typed errors).
- **react-hook-form + Zod** for forms, including the 6-step wizard.
- **Tailwind CSS** with brand **color** tokens only; a small set of hand-built accessible UI primitives (Button, Input, Label, Select, Card, Checkbox, Table, Badge) — mirrors the components the current app has, minus branding.
- **Wizard = true stepper:** six steps (Basic Info; Description & Justification; Effect on Operations; Equipment Requests with live cost sum; Economic Justification with auto payback = total_cost / annual_savings, overridable; Review & Submit). **Save Draft on every step**; Submit only on Review. `CX######` assigned at draft creation (gaps from abandoned drafts acceptable).

## 9. Workflow engine (test-first)

Pure Python helpers (in `services/workflow.py`), unit-tested with pytest before wiring:
- `compute_required_levels(total_cost, thresholds)` → `≤ L1.max → 1`; `≤ L2.max → 2`; else `3`. Every request enters at L1 and climbs to the required level.
- `resolve_assignee(level, division, thresholds)` → L1 = `division.l1_approver`; L2/L3 = the threshold level's company-wide approver; if the resolved approver has an active delegate, route to the delegate (record whom they act for).

Transactional service actions (each writes an `ApprovalAction`, triggers an email, and is guarded for concurrency):
- **submit** → strict-validate; set `total_cost`, `required_levels`; `status=PENDING_L1`, `current_level=1`; assign L1.
- **approve** → advance `current_level`; if `> required_levels` → `APPROVED`, clear assignee, notify Finance; else assign next level.
- **reject** → comment required → `REJECTED`, clear assignee, email requestor.
- **resubmit** → from `REJECTED`, restart routing at L1, full history preserved.
- **finance** → Finance role, request `APPROVED`; set category costs + `finance_completed=true`.

**Optimistic concurrency:** each action updates guarded on the expected `status`/`current_level`; if no row matches, return "already actioned by someone else."

## 10. Attachments

`services/storage.py` exposes a `StorageDriver` (`put`/`get`/`delete`): **dev** → local `uploads/` (gitignored); **prod** → **Azure Blob** (`azure-storage-blob`). `services/attachments.py` manages rows + access. Files are served only via the access-checked route (design §8) — never a public URL.

## 11. Email

`services/notify.py` exposes `send_email`: **dev** logs to console + writes `NotificationLog`; **prod** uses **M365 SMTP** (`smtplib`, env-configured). Best-effort — a send failure never blocks a workflow transition; failures are logged for the future reminder job. Notifications: assignment, decision-to-requestor, final-approval-to-Finance.

## 12. Testing

- **Backend (pytest):** workflow engine (unit — routing, advancement, rejection/resubmit, delegation, finance gating, concurrency guard); API integration (auth, role/ownership enforcement, request lifecycle, attachment access control). Test DB = SQLite.
- **Frontend (Vitest + RTL, light):** wizard step/validation logic. Manual smoke for full flows.

## 13. Dev experience

- Backend: `flask run` on `:5000`. Frontend: Vite dev server on `:5173` with a **proxy** for `/api` → `:5000` (same-origin in dev, no CORS). Prod: Flask serves the built React bundle (or a reverse proxy fronts both) — same-origin so session cookies work.
- Provide a launcher that starts both processes (replacing `run-app.bat`).

## 14. Implementation phasing

The plan will sequence roughly:
1. Backend skeleton: app factory, config, extensions, SQLAlchemy models (schema port), Alembic init, seed. **Then remove `capex-app`.**
2. Auth (login/logout/me/csrf, lockout, bcrypt) + Flask-Login + tests.
3. Frontend skeleton: Vite/React/TS, Tailwind + brand tokens, API client, route guard, login page.
4. Admin domains: users, divisions, thresholds (backend + Pydantic + React screens) to Phase-1 parity, + profile/delegate/password.
5. Workflow engine (pytest, test-first) + counter + validation schemas.
6. Request draft: create/save (backend + wizard UI, Save Draft).
7. Submit wiring + email adapter.
8. Detail page + approve/reject/resubmit/finance actions.
9. Attachments (storage adapter + service + upload UI + download route).
10. My Requests list/filters; final cutover cleanup.
