# Bid Flow — starter blueprint

A complete guide for building a **customer bid / quote application** with
workflow approval and email, extracted from the working **CAPRI** app
(United Uptime Services). Copy this file into the new repo and you start with
the layout, design tokens, buttons, page shells, approval engine, and email
stack already decided.

**How to use it:** drop this file in the new repo root, then tell Claude Code
"read BID-APP-STARTER-GUIDE.md and build milestone 1." Everything in
**§4 Design system** and **§5 API conventions** is literal copy-paste — same
stack, so it works unchanged apart from names. Everything in **§7–§11** is a
proposed design for the bid domain: sound, but confirm the business rules
before building.

**Provenance:** §2–§6, §12–§14 are battle-tested — they run in production-ish
use today. §7–§11 are new design work for bids, reasoned from the CAPEX
equivalents. Where I am proposing rather than reporting, it says so.

---

## 1. What you are building, and how it differs from CAPRI

A salesperson builds a **bid for a customer**, gets internal approval when the
pricing needs sign-off, and then sends the customer a branded PDF.

CAPRI is the same shape — a document that routes through tiered approvers
and emails people at each step — so the entire skeleton transfers. What changes
is that **the output leaves the building**.

| Concern | CAPRI | Bid Flow |
| --- | --- | --- |
| The record | `CapexRequest` (internal spend request) | `Bid` (customer-facing quote) |
| Owner | Requestor | Salesperson / bid owner |
| Third party | none | **`Customer`** — new entity, with contacts |
| Line items | `EquipmentItem` (units, cost) | `BidLineItem` (qty, unit price, discount, **cost, margin**) |
| Why approval | total cost vs. threshold caps | **four** triggers — see §8 |
| After approval | Finance fills a cost breakdown | **Send the bid to the customer** |
| Terminal states | APPROVED | SENT → ACCEPTED / DECLINED / EXPIRED |
| Revisions | edit + resubmit a rejection | **bid revisions (v1, v2 …)** are normal |
| The PDF | internal audit record | **customer deliverable** — cover, terms, validity, signature |

### The one thing to get right

CAPEX only ever mails colleagues. A bid app can mail **customers**, so a
mistake is externally visible. Two rails, both non-negotiable:

1. **Keep the Test/Live delivery mode** from §10. In Test mode every message is
   redirected to one internal address with a banner. Default to Test.
2. **Never send to a customer automatically.** Approval does *not* send. A
   human presses **Send to customer** and confirms a dialog that names the
   recipient address. (This was an explicit decision, not a default.)

---

## 2. Stack and project layout

Same stack as CAPRI, deliberately:

- **backend/** — Flask (Python 3.14), SQLAlchemy 2.0 typed `Mapped`,
  Flask-Login session auth + CSRF, Pydantic v2 request schemas, Alembic.
  SQLite in dev, Azure SQL Server in prod.
- **frontend/** — React 19 + Vite 6 + TypeScript, React Router 7, TanStack
  Query 5, Tailwind CSS v4, `lucide-react` for non-nav glyphs.
- **Single server.** Vite builds to `frontend/dist`; Flask serves that plus
  `/api`, with a catch-all returning `index.html` for client routes. One
  origin, one port (5000), no dev proxy, no CORS.
- `openpyxl` for xlsx export, `reportlab` for PDFs, `pywin32` for Outlook.

```
bid_app/
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py          # create_app: extensions, blueprints, error handlers, SPA catch-all
│  │  ├─ config.py            # DevConfig / TestConfig / ProdConfig
│  │  ├─ extensions.py        # db, migrate, login_manager, csrf
│  │  ├─ models/__init__.py   # ALL models in one file (see §7)
│  │  ├─ authz.py, roles.py, serialization.py
│  │  ├─ schemas/             # Pydantic v2 input models
│  │  ├─ blueprints/          # thin HTTP routes, one per resource
│  │  ├─ services/            # all business logic
│  │  └─ assets/              # baked email PNGs (§10)
│  ├─ migrations/             # Alembic
│  ├─ tests/                  # pytest + conftest + factories
│  ├─ requirements.txt
│  └─ seed.py
├─ frontend/
│  └─ src/
│     ├─ main.tsx, App.tsx, index.css
│     ├─ api/                 # client.ts + one module per resource
│     ├─ auth/                # useMe, ProtectedLayout, AdminLayout, loginRedirect
│     ├─ components/          # AppShell, Logo, NavIcons, ActionIcons, ui/
│     └─ routes/              # one file per page, admin/ subfolder
├─ brand/                     # logo mockups, icon sheet, palette
├─ Start Bid Flow.cmd
└─ run-app.ps1
```

**Keep every model in one `models/__init__.py`.** CAPEX has ~12 models in one
file and it is easier to reason about relationships than a package of files.

---

## 3. Setup and running

### The Windows gotcha that will waste your afternoon

If the repo path contains `&` — e.g. `D&H United Fueling Solutions` — npm's
default cmd script-shell breaks, and so does anything shelling out to
`npm run …`. Two consequences, both permanent:

1. Ship a **PowerShell** launcher (`run-app.ps1`) plus a `.cmd` shim that calls
   it. Do **not** write a `.bat` launcher — cmd's `start` mis-parses the `&`.
   Launch the server from its own directory via a *relative* path so the `&`
   never reaches a parser.
2. In CI, and whenever an agent runs frontend tooling, **call the binaries
   through node** to skip the shell entirely:

```
node ./node_modules/vite/bin/vite.js build
node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
node ./node_modules/vitest/vitest.mjs run
```

### Manual start

```bash
cd frontend && npm install && node ./node_modules/vite/bin/vite.js build
cd ../backend && python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt && flask db upgrade && python seed.py && flask run
```

App on http://localhost:5000, health at `GET /api/health` → `{"status":"ok"}`.
`run-app.ps1` should do first-run setup (venv, deps, `flask db upgrade`,
`seed.py`), build the frontend, start Flask in its own window, and open the
browser.

There is **no live dev server** — to see a frontend change, rebuild. Say so in
the new repo's CLAUDE.md or you will confuse every future session.

---

## 4. Design system — copy this verbatim

This is the part that saves the most time. It is all real, working code.

### 4.1 `index.css` — Tailwind v4 tokens and dark mode

Semantic tokens, not raw `slate-*`. Dark mode is a class-based variant
overriding the same CSS variables, so every token-based utility re-themes for
free.

```css
@import "tailwindcss";

/* Manual (class-based) dark mode: toggled via `.dark` on <html>. */
@custom-variant dark (&:where(.dark, .dark *));

@theme {
  /* Brand palette — swap these three for the bid app's brand */
  --color-brand-navy: #0B2A4A;
  --color-brand-blue: #2563EB;
  --color-brand-sky:  #93BBF5;

  /* Semantic tokens — light defaults, overridden in .dark below. */
  --color-bg: #f1f5f9;          /* app content background */
  --color-surface: #ffffff;     /* cards, panels */
  --color-surface-2: #f8fafc;   /* subtle inset (hover, insets) */
  --color-border: #e2e8f0;
  --color-fg: #0f172a;          /* primary text */
  --color-muted: #64748b;       /* secondary text */
  --color-sidebar: #0B2A4A;
  --color-sidebar-fg: #cbd5e1;
  --color-sidebar-muted: #7c93b0;
  --color-accent: #2563EB;
  --color-accent-fg: #ffffff;
}

.dark {
  --color-bg: #0b1220;
  --color-surface: #1e293b;
  --color-surface-2: #172033;
  --color-border: #334155;
  --color-fg: #f1f5f9;
  --color-muted: #94a3b8;
  --color-sidebar: #0a1f38;
  --color-sidebar-fg: #cbd5e1;
  --color-sidebar-muted: #64809f;
  --color-accent: #3b7bff;
}

html, body, #root { height: 100%; }
body { background-color: var(--color-bg); color: var(--color-fg); }

/* Edge/IE draw their own password-reveal eye, duplicating PasswordInput's
   toggle. Without this, users see two eyes. */
input::-ms-reveal, input::-ms-clear { display: none; }
```

Persist the theme in `localStorage` and apply it from an **inline script in
`index.html` before render**, or you get a flash of the wrong theme.

### 4.2 Primitives

`components/ui/Button.tsx`:

```tsx
import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-accent-fg hover:opacity-90',
  secondary: 'border border-border bg-surface text-fg hover:bg-surface-2',
  ghost: 'text-fg hover:bg-surface-2',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

export function Button({ className = '', variant = 'primary', ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold transition disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  )
}
```

`components/ui/Input.tsx` and `Select.tsx` are the same idea — spread props,
one class string, token colors:

```tsx
export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg outline-none placeholder:text-muted focus:border-accent ${className}`}
      {...props}
    />
  )
}

export function Select({ className = '', ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={`w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg outline-none focus:border-accent ${className}`}
      {...props}
    />
  )
}
```

`components/ui/Card.tsx`:

```tsx
export function Card({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`rounded-xl border border-border bg-surface shadow-sm ${className}`} {...props} />
}

export function StatCard({ label, value, sub, accent = false }: {
  label: string; value: ReactNode; sub?: ReactNode; accent?: boolean
}) {
  return (
    <Card className="p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${accent ? 'text-accent' : 'text-fg'}`}>{value}</div>
      {sub != null && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </Card>
  )
}
```

### 4.3 Status badges

Tone map + status map. For bids, extend the status list (§9):

```tsx
type Tone = 'slate' | 'blue' | 'amber' | 'green' | 'red'

const TONES: Record<Tone, string> = {
  slate: 'bg-slate-100 text-slate-600 dark:bg-slate-500/15 dark:text-slate-300',
  blue:  'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  amber: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  red:   'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
}

export function Badge({ tone = 'slate', icon, children }: {
  tone?: Tone; icon?: ReactNode; children: ReactNode
}) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}>
      {icon}{children}
    </span>
  )
}

// Bid Flow tones — extend CAPEX's set for the post-approval states
const STATUS_TONE: Record<string, Tone> = {
  DRAFT: 'slate',
  PENDING_L1: 'amber', PENDING_L2: 'amber', PENDING_L3: 'amber',
  APPROVED: 'green', REJECTED: 'red',
  SENT: 'blue', ACCEPTED: 'green', DECLINED: 'red', EXPIRED: 'slate',
}
```

`StatusBadge` looks up tone + label + icon and renders `<Badge>`. Keep the
label map separate from the tone map so wording changes never touch color.

### 4.4 `BrandCard` — the page pattern

**The single most reusable piece.** Every main page wraps its content in
**exactly one** `BrandCard`: a rounded card with a navy header band, a per-page
mark in a soft rounded tile, white title, sky subtitle, and optional
subheader/actions/footer slots. It deliberately mirrors the notification-email
look, so the app and its emails feel like one product.

```tsx
import type { ReactNode } from 'react'
import { /* your nav icons */ type NavIconProps } from '../NavIcons'

const NAVY = '#0B2A4A'
const SKY = '#93BBF5'
const MARK_BLUE = '#5B9BFF'

export type PageMark = 'dashboard' | 'newBid' | 'bids' | 'customers'
  | 'users' | 'approvalRules' | 'emailTemplates' | 'profile' | 'reports'

const MARKS: Record<PageMark, React.ComponentType<NavIconProps>> = { /* key -> icon */ }

export function BrandCard({
  title, subtitle, actions, subheader, footer,
  mark = 'dashboard', bodyClassName = 'px-7 py-6', className = '', children,
}: {
  title: ReactNode
  subtitle?: ReactNode
  /** Right side of the navy band (status badge, primary button). */
  actions?: ReactNode
  /** Band between header and body (stepper, filters) — caller styles it. */
  subheader?: ReactNode
  /** Footer action bar; the wrapper supplies flex + gap + padding. */
  footer?: ReactNode
  mark?: PageMark
  bodyClassName?: string
  className?: string
  children: ReactNode
}) {
  const Mark = MARKS[mark]
  return (
    <div className={`overflow-hidden rounded-2xl border border-border bg-surface shadow-sm ${className}`}>
      <div className="flex items-center gap-3.5 px-7 py-5" style={{ background: NAVY }}>
        <div className="flex h-[46px] w-[46px] shrink-0 items-center justify-center rounded-xl"
             style={{ background: 'rgba(91,155,255,0.16)', color: MARK_BLUE }}>
          <Mark size={24} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-bold text-white">{title}</h1>
          {subtitle && <div className="text-[13px] tracking-wide" style={{ color: SKY }}>{subtitle}</div>}
        </div>
        {actions}
      </div>
      {subheader}
      <div className={bodyClassName}>{children}</div>
      {footer && <div className="flex items-center gap-3 border-t border-border px-7 py-4">{footer}</div>}
    </div>
  )
}
```

Rules that keep it coherent:

- **One `BrandCard` per main page**, with that page's own `mark`.
- Secondary edit forms (a customer form, an email-template editor) use plain
  headings, not a second BrandCard.
- The wizard uses the `subheader` slot for its stepper and `footer` for its
  action bar — same component, no variant needed.

### 4.5 `AppShell` — sidebar and header

Navy sidebar with grouped, role-filtered nav and an active pill; header with
the user's name, a theme toggle, and Sign Out; `<Outlet/>` for the page.

```tsx
interface NavItem {
  to: string
  label: string
  icon: React.ComponentType<NavIconProps>
  roles: string[]                 // empty = everyone
  end?: boolean
  /** Extra paths that also mark this item active (e.g. the wizard's edit route). */
  activePattern?: RegExp
}

const NAV_SECTIONS: { section: string; items: NavItem[] }[] = [
  { section: 'Overview', items: [
    { to: '/',          label: 'Dashboard', icon: DashboardIcon, roles: [], end: true },
    { to: '/bids/new',  label: 'New Bid',   icon: NewBidIcon,    roles: [],
      activePattern: /^\/bids\/[^/]+\/edit$/ },
    { to: '/bids',      label: 'My Bids',   icon: BidsIcon,      roles: [], end: true },
    { to: '/customers', label: 'Customers', icon: CustomersIcon, roles: [] },
    { to: '/reports',   label: 'Reports',   icon: ReportsIcon,   roles: ['SALES_MANAGER', 'ADMIN'] },
  ]},
  { section: 'Admin', items: [
    { to: '/admin/users',           label: 'Users',           icon: UsersIcon,          roles: ['ADMIN'] },
    { to: '/admin/approval-rules',  label: 'Approval Rules',  icon: RulesIcon,          roles: ['ADMIN'] },
    { to: '/admin/email-templates', label: 'Email Templates', icon: EmailTemplatesIcon, roles: ['ADMIN'] },
  ]},
  { section: 'Account', items: [
    { to: '/profile', label: 'My Profile', icon: ProfileIcon, roles: [] },
  ]},
]
```

The shell filters items by role and drops empty sections:

```tsx
const roles = user?.roles ?? []
const can = (item: NavItem) => item.roles.length === 0 || item.roles.some((r) => roles.includes(r))
const sections = NAV_SECTIONS
  .map((s) => ({ ...s, items: s.items.filter(can) }))
  .filter((s) => s.items.length > 0)
```

Layout and the active-pill class:

```tsx
<div className="flex min-h-screen bg-bg text-fg">
  <aside className="flex w-60 shrink-0 flex-col bg-sidebar text-sidebar-fg">
    {/* logo + product name block, border-b border-white/10 px-5 py-4 */}
    <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
      {/* section label: text-[11px] font-semibold uppercase tracking-wider text-sidebar-muted */}
      <NavLink className={({ isActive }) => {
        const active = isActive || (item.activePattern?.test(pathname) ?? false)
        return `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition ${
          active ? 'bg-accent text-white' : 'text-sidebar-fg hover:bg-white/10 hover:text-white'}`
      }} />
    </nav>
  </aside>
  <div className="flex flex-1 flex-col">
    <header className="flex items-center justify-between gap-3 border-b border-border bg-surface px-6 py-3">…</header>
    <main className="flex-1 overflow-y-auto p-6"><Outlet /></main>
  </div>
</div>
```

On sign-out, call `logout()` then **`queryClient.clear()`** before navigating,
or the next user briefly sees cached data.

### 4.6 Icons

Two custom sets, both 24px grid, rounded joins, `stroke="currentColor"` so they
take their parent's color:

- **`NavIcons.tsx`** — one distinct symbol per page, used by the sidebar and by
  `BrandCard`'s mark.
- **`ActionIcons.tsx`** — in-page glyphs: Approve/Reject/Submit/Send, row
  controls (View/Edit/Delete/Download/Search/Filter/Add/Upload), and
  workflow-status icons used by `StatusBadge`.

Shared wrapper:

```tsx
export interface NavIconProps { size?: number }

function Icon({ size = 24, children }: NavIconProps & { children: React.ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth={1.8}
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  )
}

export function DashboardIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <rect x="3" y="3"  width="7" height="9" rx="1.6" />
      <rect x="14" y="3" width="7" height="5" rx="1.6" />
      <rect x="14" y="12" width="7" height="9" rx="1.6" />
      <rect x="3" y="16" width="7" height="5" rx="1.6" />
    </Icon>
  )
}
```

Use `lucide-react` only for incidental glyphs (Sign Out, chevrons). Keep nav
and action icons custom so they stay visually consistent.

### 4.7 Data tables

Header rows use the sky brand tint — plain `surface-2` reads too subtle and
solid navy too bold. Every new table should match:

```tsx
<thead>
  <tr className="border-b border-border bg-brand-sky/25 text-left text-xs uppercase
                 tracking-wide text-brand-navy dark:bg-brand-sky/10 dark:text-brand-sky
                 [&>th]:py-1.5 [&>th:first-child]:pl-2 [&>th:last-child]:pr-2">
```

Put sort comparators and filtering in a **separate pure module**
(`routes/bidsSort.ts`) and unit-test them — status should sort in *workflow
order*, not alphabetically, and blanks go last in both directions. Wide tables
scroll inside their own `overflow-x-auto` container; the page body never scrolls
sideways.

---

## 5. API conventions

### 5.1 The fetch wrapper

One `api()` helper handles CSRF, cookies, and error shape. Same-origin, so
`credentials: 'include'` and a relative `/api` prefix are all you need.

```ts
let csrfToken: string | null = null

export class ApiError extends Error {
  status: number
  code?: string
  constructor(status: number, message: string, code?: string) {
    super(message); this.name = 'ApiError'; this.status = status; this.code = code
  }
}

// 400/401/403 can mean a stale cached token — drop it so the next call refetches.
function _clearsCsrf(status: number): boolean {
  return status === 400 || status === 401 || status === 403
}

async function ensureCsrf(): Promise<string> {
  if (csrfToken) return csrfToken
  const res = await fetch('/api/auth/csrf', { credentials: 'include' })
  if (!res.ok) throw new ApiError(res.status, 'Could not obtain a CSRF token.')
  csrfToken = (await res.json()).csrfToken as string
  return csrfToken
}

export async function api<T = unknown>(
  path: string, options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = options.method ?? 'GET'
  const headers: Record<string, string> = {}
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (method !== 'GET' && method !== 'HEAD') headers['X-CSRFToken'] = await ensureCsrf()

  const res = await fetch(`/api${path}`, {
    method, credentials: 'include', headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (!res.ok) {
    if (_clearsCsrf(res.status)) csrfToken = null
    let message = res.statusText, code: string | undefined
    try {
      const data = await res.json()
      if (data?.error) message = data.error
      if (data?.code) code = data.code
    } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, message, code)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
```

Add an `apiUpload(path, formData)` twin for file uploads (no `Content-Type`;
let the browser set the multipart boundary). In `main.tsx`, make a global 401
handler redirect to `/login?next=<path>` so deep links survive.

### 5.2 Thin routes, fat services

Routes validate input with a Pydantic schema and delegate. All logic lives in
`services/`. Handled failures raise `ServiceError`:

```python
class ServiceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status
```

Registered once in `create_app`:

```python
@app.errorhandler(ServiceError)
def _handle_service_error(err):
    return jsonify(error=err.message), err.status

@app.errorhandler(ValidationError)                      # pydantic
def _handle_validation_error(err):
    # NOTE: use include_context=False. err.errors() embeds the raw ValueError
    # from any raising field_validator in `ctx`, and jsonify cannot serialize
    # it — you get a 500 instead of a 400. This bit CAPRI; don't inherit it.
    return jsonify(error="Validation failed.", details=err.errors(include_context=False)), 400
```

**Notifications fire from blueprints, never from services.** Services stay
email-free and therefore easy to test.

### 5.3 Money and numbers

- Money columns: `Numeric(18, 2)`. Ratios/percentages: `Numeric(9, 4)`.
- Serialize money as a **clean string**, never a float:

```python
def money_str(value: Optional[Decimal]) -> Optional[str]:
    """No trailing zeros, no scientific notation, or None."""
    if value is None:
        return None
    s = format(value, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s
```

Use it for ratio columns too, or a `Numeric(9,4)` margin prints `18.5000`.
Do cents math in integers when comparing totals for equality.

---

## 6. Auth and roles

Flask-Login sessions + CSRF. Email-based login. A 30-day remember-me cookie so
emailed deep links survive a browser restart (`REMEMBER_COOKIE_*` in config).

Roles are a **JSON string array on `User`** with a `roles_list` property — no
join table, since roles are a short fixed list and a user holds several.

```python
ROLES = ["SALES", "SALES_MANAGER", "FINANCE", "ADMIN"]   # bid app's set

def serialize_roles(roles) -> str:
    return json.dumps([r for r in ROLES if r in roles])  # known roles, canonical order
```

Guard routes with a decorator; **any one** of the listed roles suffices:

```python
def require_roles(*roles):
    def decorator(fn):
        @login_required
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not any(r in current_user.roles_list for r in roles):
                return jsonify(error="Forbidden."), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
```

Row-level visibility belongs in the service, and **every route that returns or
acts on one record should go through the same accessor** so authorization can't
drift:

```python
def _can_view(bid, viewer):
    if viewer.id in (bid.owner_id, bid.assignee_id):
        return True
    roles = viewer.roles_list
    return "ADMIN" in roles or "FINANCE" in roles or "SALES_MANAGER" in roles

def get_bid(bid_id, viewer):
    bid = db.session.get(Bid, bid_id)
    if bid is None:
        raise ServiceError("Bid not found.", 404)
    if not _can_view(bid, viewer):
        raise ServiceError("You do not have access to this bid.", 403)
    return bid
```

New users and admin password resets start at a `DEFAULT_PASSWORD` with
`must_change_password` set. An app-level `before_request` then blocks the whole
API with 403 `PASSWORD_CHANGE_REQUIRED`, exempting only set-password, me,
csrf-token, and logout — that forces the change screen without special-casing
every route. If the default password constant ever changes, grep for the
literal: it tends to be duplicated in UI copy.

---

## 7. Data model for bids

**Proposed — confirm with the business before building.** Money `Numeric(18,2)`,
ratios `Numeric(9,4)`.

**`Customer`** — `number`, `name`, `active`, billing/shipping address fields,
`payment_terms`, optional `owner_id` (account rep).

**`CustomerContact`** — `customer_id`, `name`, `email`, `phone`, `title`,
`is_primary`. Bids email a *contact*, not a free-typed address; that alone
prevents a class of send-to-the-wrong-person mistakes.

**`Bid`** — the core record:

- Identity: `number` (`BID000001…` from a `Counter` row, see below),
  `revision` (int, starts 1), `parent_bid_id` (nullable, links a revision to
  its predecessor), `status`.
- Parties: `customer_id`, `contact_id`, `owner_id` (salesperson),
  `assignee_id` (current approver — a display hint only, see §8).
- Dates: `bid_date`, `valid_until`, `sent_at`, `decided_at`.
- Commercial totals, all stored (not recomputed on read):
  `subtotal`, `discount_total`, `total`, `cost_total`, `margin_amount`,
  `margin_pct`.
- Terms: `payment_terms`, `delivery_terms`, `warranty_terms`, `freight_terms`,
  `notes_to_customer`, `internal_notes`.
- Approval-trigger flags (§8): `nonstandard_terms`, `special_pricing`.
- Workflow: `required_levels`, `current_level`.

**`BidLineItem`** — `bid_id`, `sort_order`, `description`, `part_number`,
`qty`, `unit`, `list_price`, `unit_price`, `discount_pct`, `unit_cost`,
`extended_price`, `extended_cost`, `is_optional`. Sums drive the bid totals.

**`ApprovalRule`** — replaces CAPEX's `ApprovalThreshold`, because bids have
four triggers instead of one. One row per level (1/2/3):

- `level`, `approvers` (many-to-many — the pool)
- `max_total` (null at top level = no cap)
- `min_margin_pct` (approval required below this)
- `max_discount_pct` (approval required above this)

**`ApprovalAction`** — the audit trail, unchanged from CAPEX and load-bearing:
`bid_id`, `actor_id`, `acted_for_id` (set when a delegate acted), `action`
(`SUBMITTED` / `APPROVED` / `REJECTED` / `RESUBMITTED` / `SENT_TO_CUSTOMER` /
`CUSTOMER_ACCEPTED` / `CUSTOMER_DECLINED`), `level`, `comment`, `created_at`.

**Also carry over:** `Attachment`, `NotificationLog`, `Counter` (for
gap-free document numbers), `AppSetting` (key/value app settings),
`EmailTemplate` (§10).

Two habits worth keeping:

- **Store computed totals.** Recomputing margin on every read makes list pages
  and reports slow and inconsistent. Recompute on save.
- **A `Counter` table, not `max(id)+1`**, for customer-visible numbers.

---

## 8. Approval workflow

The CAPEX engine transfers almost intact. Adapt the *trigger*, keep the
*mechanics*.

### 8.1 Levels and pools

- Each level has a **pool** of approvers, and **any one** of them may act.
- Every approver maps through their out-of-office **delegate**.
- The pool appears on every member's worklist; `assignee_id` is only a display
  hint (the first eligible approver), never the authorization check.

```python
def intended_approvers(level, rules):
    match = next((r for r in rules if r.level == level), None)
    return list(match.approvers) if match else []

def effective_assignee(user):
    if user is None:
        return None
    return user.delegate if user.delegate_id else user

def eligible_actors(level, rules):
    """Configured approvers mapped through delegates, de-duplicated."""
    seen, out = set(), []
    for approver in intended_approvers(level, rules):
        actor = effective_assignee(approver)
        if actor is not None and actor.id not in seen:
            seen.add(actor.id)
            out.append(actor)
    return out
```

### 8.2 What triggers approval — all four

Confirmed: **total value, discount/margin floor, non-standard terms, and special
pricing/cost overrides.** Compute the required level as the **highest** level
any trigger demands, so the strictest condition wins:

```python
def compute_required_levels(bid, rules) -> int:
    """Highest level demanded by any trigger. 0 = no approval needed."""
    needed = 0
    ordered = sorted(rules, key=lambda r: r.level)

    # 1. Total value — lowest level whose cap covers the total.
    for r in ordered:
        if r.max_total is None or bid.total <= r.max_total:
            needed = max(needed, r.level)
            break
    else:
        needed = max(needed, ordered[-1].level)

    # 2. Margin floor / 3. discount ceiling — each rule that is breached
    #    demands at least its own level.
    for r in ordered:
        if r.min_margin_pct is not None and bid.margin_pct < r.min_margin_pct:
            needed = max(needed, r.level)
        if r.max_discount_pct is not None and bid.discount_pct > r.max_discount_pct:
            needed = max(needed, r.level)

    # 4. Non-standard terms or special pricing — always at least level 2,
    #    because these are judgment calls a manager should see.
    if bid.nonstandard_terms or bid.special_pricing:
        needed = max(needed, 2)

    return needed
```

Two things to decide with the business, because I guessed:

- Whether breaching margin should force the **top** level rather than the level
  whose floor was breached.
- Whether non-standard terms should be **level 2** or the top level.

Make the rule visible in the UI. On the Review step and the bid detail page,
say *why* approval is needed ("margin 14.2% is below the 18% floor for Level
2"). Approvers act faster when the reason is on the screen, and salespeople
learn the rules.

### 8.3 Transitions are guarded

Two approvers can click Approve simultaneously. Guard on **both** level and
status with a conditional UPDATE and check `rowcount`:

```python
def _guarded_transition(bid_id, expected_level, expected_status, values):
    stmt = (sql_update(Bid)
            .where(Bid.id == bid_id,
                   Bid.current_level == expected_level,
                   Bid.status == expected_status)
            .values(**values))
    if db.session.execute(stmt).rowcount != 1:
        raise ServiceError("This bid was already actioned by someone else.", 409)
```

Guarding on status too is what protects terminal transitions (final approve,
reject) that don't change `current_level`.

Record `acted_for_id` when a delegate acted, so the trail shows both people:

```python
def _acted_for(bid, level, actor_id, rules):
    for approver in intended_approvers(level, rules):
        actor = effective_assignee(approver)
        if actor is not None and actor.id == actor_id and approver.id != actor_id:
            return approver.id
    return None
```

### 8.4 Opening the workflow

Validate before routing, and give a specific message per failure — these are
the errors users actually hit:

```python
def _open_workflow(bid):
    if not bid.line_items:
        raise ServiceError("Add at least one line item.")
    if bid.customer is None or bid.contact is None:
        raise ServiceError("A customer and contact are required.")
    if bid.valid_until is None:
        raise ServiceError("Set a validity date before submitting.")
    recompute_totals(bid)
    rules = approval_rule_service.list_rules()
    bid.required_levels = compute_required_levels(bid, rules)
    if bid.required_levels == 0:                 # priced within policy
        bid.status = "APPROVED"
        return
    bid.current_level = 1
    bid.status = "PENDING_L1"
    first = eligible_actors(1, rules)
    if not first:
        raise ServiceError("No level-1 approver is configured.")
    bid.assignee_id = first[0].id
```

Note the branch CAPEX doesn't have: **a bid priced inside policy needs no
approval at all** and goes straight to APPROVED, ready to send. Don't force
salespeople through an approval queue for a standard-margin quote.

---

## 9. Bid lifecycle past approval

```
DRAFT ──submit──> PENDING_L1 ─> PENDING_L2 ─> PENDING_L3 ──> APPROVED
  ^                   │                                         │
  │                   └──reject──> REJECTED ──edit/resubmit──────┘
  │                                                             │
  └──── new revision (v2) ←── DECLINED / EXPIRED     "Send to customer"
                                                                │
                                              SENT ──> ACCEPTED / DECLINED
                                                   └──> EXPIRED (valid_until passed)
```

- **APPROVED means "cleared to send", not "sent."** Keep them distinct or you
  can never tell whether the customer has actually seen it.
- **SENT** is set only by the explicit send action (§10.4), stamping `sent_at`.
- **ACCEPTED / DECLINED** are recorded by the salesperson, with `decided_at`.
- **EXPIRED** is derived from `valid_until`. Compute it on read at first — a
  nightly job to flip the column is a later optimization, not a v1 requirement.
- **Revisions:** copy the bid and its line items into a new row with
  `revision + 1` and `parent_bid_id` set, back to DRAFT. Never mutate a bid the
  customer has already seen — you lose the record of what was quoted. Show the
  revision chain on the detail page.

Editing rules, mirroring CAPEX's attachment permissions: the owner edits while
DRAFT or REJECTED; nobody edits once SENT (make a revision instead).

---

## 10. Email

> **Full spec:**
> `docs/superpowers/specs/2026-07-28-bid-app-email-system-design.md` takes this
> section to implementation depth — module boundaries, the three-tier template
> defaults, the render pipeline, the bid template catalog with tokens and
> shipped defaults, the audience flag for customer-facing mail, the API and
> editor UI, the testing contract, and a copy/adapt/rewrite port checklist.
> This section remains the summary.

### 10.1 The frame, and why it is images

Classic Outlook renders email with **Microsoft Word's engine**. It ignores
`border-radius`, ignores div layout and padding on `<a>`, and **mangles VML on
send** — but it renders images perfectly. So bake rounded chrome into PNGs
(header band, CTA buttons, bottom strip) at 2x, display at 1x, and keep
everything else table-based with inline CSS and `bgcolor` on `<td>`.

This repo has the full recipe in **`email-rounded-corners-guide.md`** — read
it before touching email markup. It includes a Pillow generator for the PNGs
and the Content-ID attachment code.

### 10.2 Editable templates

One `EmailTemplate` row per type, created only once customized; shipped
defaults live in code (`DEFAULTS`). Each row carries live
`subject`/`body_html`/`enabled` plus `default_subject`/`default_body_html` so an
admin can reset to their own baseline. Admins edit subject, body (WYSIWYG), and
the enabled flag under **Admin → Email Templates**, with `{token}` placeholders
substituted at send time inside a locked brand frame.

Suggested types for the bid app:

| Type | To | When |
| --- | --- | --- |
| `APPROVAL_NEEDED` | approver pool at the current level | on submit / advance |
| `BID_APPROVED` | owner | final approval |
| `BID_REJECTED` | owner | rejection, with the comment |
| `BID_SENT` | owner (confirmation copy) | after a customer send |
| `CUSTOMER_BID` | **the customer contact** | the explicit send action |

Keep the token set small and shared: `{number}`, `{customer}`, `{total}`,
`{valid_until}`, `{owner}`, `{link}`, plus `{comment}` for rejections.

Three hard-won rules:

- **Editable bodies must stay round-trippable through the WYSIWYG editor.**
  Quill strips tables, `bgcolor`, and VML — a saved button once became
  invisible white-on-white text. Structural pieces belong in the locked frame,
  not the editable body. Paragraphs, bold, and blockquote are safe.
- **Preview HTML must equal sent HTML.** Render both with the same frame
  function, swapping only the image `src` resolver (`cid:` when sending,
  `data:` in the browser). Pin it with a test.
- **Verify against a real Outlook render**, not a browser. Send yourself a
  sample and look at it.

Adding a template type needs a CTA button PNG — but check the existing buttons
first; a generic label like "View the bid" is reusable across several types and
saves making new artwork.

### 10.3 Delivery mode — the safety rail

An `AppSetting`-backed runtime mode, toggled by admins:

- **Test** — redirect *every* message to one configurable internal recipient
  and prepend a "redirected while testing" banner. `NotificationLog` still
  records the *intended* recipient.
- **Live** — send to real recipients.

Default to **Test**, and keep a separate `EMAIL_ENABLED` config flag gating
whether anything is sent at all. In a bid app this is what stands between a
test run and a customer receiving a fake quote. Show the current mode in the
UI where sending happens, not just on the admin page.

### 10.4 Sending to the customer — explicit only

Decided: **the app sends, but never automatically.**

- Approval sends *internal* mail only.
- A **Send to customer** button appears on an APPROVED bid, for the owner (and
  managers/admin).
- Clicking it opens a confirmation that **names the recipient address and the
  attachment**: "Send bid BID000123 (PDF) to jane.doe@acme.com?"
- Only on confirm does the app send `CUSTOMER_BID`, set `status = SENT`, stamp
  `sent_at`, log an `ApprovalAction` of `SENT_TO_CUSTOMER`, and write a
  `NotificationLog` row.
- Re-sending is allowed and logged; each send appends to the trail.

Route it as `POST /api/bids/<id>/send`, guarded so it 400s unless the bid is
APPROVED (or SENT, for a deliberate re-send) and has a contact with an email.

### 10.5 Attachments

Outlook COM attaches from a **path**, not bytes, so write each attachment to a
temp file and clean up after `Send()`:

```python
def send(to, subject, body, html=None, attachments=None):
    """attachments: list of (filename, bytes) — ordinary visible attachments,
    unlike the inline brand assets, which are keyed by Content-ID."""
    tmpdir = tempfile.mkdtemp(prefix="bidflow-mail-") if attachments else None
    pythoncom.CoInitialize()
    try:
        mail = win32com.client.Dispatch("Outlook.Application").CreateItem(0)
        mail.To, mail.Subject = to, subject
        if html is not None:
            _attach_inline_assets(mail, html)   # cid: brand PNGs
            mail.HTMLBody = html
        else:
            mail.Body = body
        for filename, data in attachments or []:
            path = os.path.join(tmpdir, filename)
            with open(path, "wb") as fh:
                fh.write(data)
            mail.Attachments.Add(path)
        mail.Send()
    finally:
        pythoncom.CoUninitialize()
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
```

Keep `services/notify.py` as the **only** caller of the mail backend, so
swapping Outlook COM for SMTP or Microsoft Graph on a server is a one-file
change. Every send should write a `NotificationLog` row even when delivery is
disabled, and delivery failures should be logged, never raised into the request.

---

## 11. The customer-facing PDF

`reportlab` — pure Python, pip-installable, **no system libraries**. WeasyPrint
would let you reuse HTML but needs GTK/Pango native libs on Windows; skip it.

Split content from rendering. It makes the content rules testable without
parsing PDF bytes, which is the difference between real tests and none:

```python
def bid_pdf_sections(bid) -> list[dict]:
    """Plain dicts describing the document. No reportlab import here."""

def render_pdf(sections, title) -> bytes:
    """The only reportlab-aware function."""

def build_bid_pdf(bid) -> bytes: ...
def pdf_filename(bid) -> str:      # "BID000123-r2.pdf"
```

This is a **customer deliverable**, so it needs more than CAPEX's internal
record:

1. Branded header band (reuse the email header PNG for consistency).
2. Bid number **and revision**, date, and **"Valid until <date>"** prominently.
3. Customer block (company, contact, addresses) and your rep's name and contact.
4. Line-item table: description, part number, qty, unit price, extended price.
   **Show list price and discount only if you want the customer to see them** —
   a deliberate choice, so make it a flag.
5. Optional/alternate items in a clearly separate section, excluded from the
   total.
6. Totals: subtotal, discount, freight/tax if applicable, **total**.
7. Terms: payment, delivery, warranty, freight; then notes to the customer.
8. Acceptance block: signature, printed name, title, date, PO number.
9. Footer: company details and page numbers.

**Never put internal figures in the customer PDF** — no `unit_cost`,
`extended_cost`, `margin_pct`, or `internal_notes`. Build the internal copy as
a *separate* section list that adds a cost/margin block, and gate it behind a
`?internal=1` parameter restricted to managers. Write a test asserting the
customer PDF's sections contain no cost or margin keys; it is exactly the kind
of mistake that is embarrassing and easy to make.

Serve it at `GET /api/bids/<id>/pdf`, authorized by the same `get_bid()`
accessor as the detail page, returning
`Content-Disposition: attachment; filename="BID000123-r2.pdf"`. Generate on
demand; don't store.

---

## 12. Multi-step wizard

The bid builder wants a stepper: Customer → Line items → Pricing & terms →
Attachments → Review.

**Learn from CAPEX's mistake here.** Its wizard hardcoded steps as an array and
rendered bodies by positional index (`step === 4 && <Economic/>`). The moment
we needed to hide a step, every number after it was wrong and the fix touched
the whole file. Build it as a **keyed registry from day one**:

```ts
export type SectionKey = 'customer' | 'line_items' | 'pricing' | 'attachments' | 'review'

export interface Section { key: SectionKey; label: string; always?: boolean }

export const ALL_SECTIONS: Section[] = [
  { key: 'customer',    label: 'Customer',    always: true },
  { key: 'line_items',  label: 'Line Items',  always: true },
  { key: 'pricing',     label: 'Pricing & Terms' },
  { key: 'attachments', label: 'Attachments' },
  { key: 'review',      label: 'Review',      always: true },
]

export function visibleSections(hidden: string[]): Section[] {
  return ALL_SECTIONS.filter((s) => s.always || !hidden.includes(s.key))
}

/** The config can change mid-session; never let the index point past the end. */
export function clampStep(step: number, count: number): number {
  if (!Number.isFinite(step) || step < 0) return 0
  return Math.min(step, count - 1)
}
```

Render bodies by `key`, and take step numbers from the position in the
**visible** list — then hiding a section renumbers everything with no
arithmetic anywhere else. If you also want admin-configurable visibility, store
the hidden keys as a JSON array in one `AppSetting` row and expose
`GET` (any signed-in user — the wizard needs it) and `PUT` (admin only).

Other wizard behaviors worth copying:

- **New bids create nothing until the first Save/Submit.** Opening the wizard
  writes no row; the first save does `createDraft` then `updateDraft` and swaps
  the URL to `/bids/:id/edit`. Otherwise abandoned drafts pile up.
- Existing drafts **auto-save on Next** and on stepper clicks.
- The wizard edits DRAFT *and* REJECTED bids; the Review action calls
  `resubmit` when the loaded bid is REJECTED, else `submit`.
- Attach-file UI is a button over a hidden `<input type="file">`; picking a file
  uploads immediately.

---

## 13. Testing

- Backend: `cd backend && pytest -q`. CAPEX runs ~236 tests; aim for similar
  coverage of workflow transitions and authorization.
- Frontend: `node ./node_modules/vitest/vitest.mjs run`, plus
  `tsc --noEmit` and a `vite build`. Run backend tests **and** the frontend
  typecheck after any change touching both.
- `conftest.py` gives an `app` fixture on in-memory SQLite and a `client`
  fixture; `factories.py` builds users, customers, and bids in one line.

What to test, learned from what actually broke:

- **Every workflow transition**, including the concurrency guard (two approvers,
  second gets 409) and delegate routing.
- **Authorization per route**: owner 200, unrelated user 403, anonymous 401.
  Do this for the PDF endpoint too.
- **Pure modules directly** — approval-rule evaluation, sort comparators, PDF
  section builders, money formatting. These are cheap and catch the most.
- **Email**: intended recipient logged, Test mode redirects, Live mode doesn't,
  the customer template renders its tokens, and the attachment reaches the send
  function. Spy on the mail backend — never send in tests.
- **The customer PDF contains no cost/margin fields.**

When you extend a shared signature (like adding `attachments=` to the mail
sender), fix the existing spies rather than working around them.

---

## 14. Gotchas worth inheriting

Each of these cost real time in CAPRI:

1. **A field missing from the Pydantic schema is silently dropped.** The PATCH
   route does `BidDraft(**json).model_dump(exclude_unset=True)`, so a field
   absent from the schema vanishes even though the model and serializer support
   it. A new editable field must be added in **all** of: model, serializer,
   Pydantic schema, frontend type, and the form↔payload mappers.
2. **The Pydantic error handler's `ctx` bug** — see §5.2. Use
   `errors(include_context=False)`, or express constraints as types (`Literal`,
   bounds) instead of raising validators.
3. **Don't mirror a query into state with `useEffect`.** It lags a render and
   clobbers unsaved edits when the query refetches. Derive instead:
   `const value = edits ?? data ?? fallback`, and gate rendering on `data`.
4. **Quill strips tables/`bgcolor`/VML** from editable email bodies (§10.2).
5. **`Numeric(9,4)` prints `3.0000`.** Format ratios through `money_str`.
6. **Treat `created_at` as UTC** when formatting in the browser; older rows may
   arrive without a zone marker, so append `Z` if absent.
7. **A detail page shows "Loading…" forever on a 404 id** unless you handle the
   error state. Easy to miss in dev.
8. **Attachment uploads accept any type and size** unless you add a cap and an
   allowlist. Do it early — it is on CAPEX's someday list and shouldn't be.
9. **Keep docs in the repo and update them with each change.** A `CLAUDE.md`
   describing stack, layout, workflow, and gotchas is what lets an agent work
   on this without rediscovering everything. Commit docs with the code change,
   not in a batch afterwards.

---

## 15. Suggested build order

Each milestone should end green: tests pass, typecheck clean, build clean, docs
updated, one focused commit.

1. **Skeleton** — Flask + Vite single-server, health endpoint, `index.css`
   tokens, `Button`/`Input`/`Select`/`Card`, `AppShell`, login, `useMe`,
   protected routes, `run-app.ps1`. Verify: sign in and see an empty dashboard.
2. **Users, roles, auth hardening** — admin user CRUD, roles via a dual-listbox
   transfer control (not checkboxes), forced password change, delegates.
3. **Customers & contacts** — CRUD, search, the `BrandCard` page pattern, the
   sky-tinted table header, sortable list.
4. **Bids: draft + line items** — model, `Counter` numbering, wizard as a keyed
   registry, totals and margin recomputed on save, drafts deletable by owner.
5. **Approval workflow** — `ApprovalRule` admin page, the four triggers,
   pools + delegates, guarded transitions, audit trail, worklists, detail page
   with Approve/Reject and history. Show *why* approval is required.
6. **Internal emails** — baked PNG frame, editable templates, delivery mode
   defaulting to Test, `NotificationLog`. Verify with a real Outlook render.
7. **Customer PDF** — split sections/render, customer vs. internal variants,
   the no-cost-leakage test, download endpoint.
8. **Send to customer** — explicit button, confirmation naming the recipient,
   SENT status, `sent_at`, trail entry, owner confirmation copy.
9. **Outcomes & revisions** — ACCEPTED/DECLINED recording, `valid_until`
   expiry, revision cloning with the chain shown on the detail page.
10. **Reporting** — bids by status/month/salesperson, win rate, average margin,
    average days-to-decision, xlsx export of the filtered list.

Start at 1 and don't skip 6's Outlook verification — every email problem in
CAPRI was invisible in a browser preview.
