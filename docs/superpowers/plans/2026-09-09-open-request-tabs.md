# Open-Request Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A strip of tabs across the top of every CAPRI page, one per CAPEX request the user has open, so switching between requests is one click from anywhere — a port of SCORE's bid tab strip.

**Architecture:** Frontend only — no route, migration or serializer changes. A `localStorage`-backed store (`openRequests.ts`, keyed per user, cap 8, insertion order, `seq` for eviction) holds `{id, number, title, mode, step, seq}` per tab. A `RequestTabs` strip in `AppShell` reads the active tab from the URL and renders nothing when empty. The two request pages call `touchOpenRequest` when their request loads (`mode: 'view'` on the detail page, `'edit'` in the wizard); the wizard's step moves out of `useState` into the tab record so switching tabs never carries request A's step onto request B; both pages gain a "request unavailable → Close this tab" branch.

**Tech Stack:** React 19, React Router 7, TanStack Query 5, Tailwind v4, vitest 3 + jsdom + Testing Library, `lucide-react`. Node 26 (so the `localStorage` shim in §7 of the spec is required).

**Spec:** `docs/superpowers/specs/2026-09-09-open-request-tabs-design.md`

## Global Constraints

- **Repo:** `capex_tracking/` (CAPRI); all paths below are relative to `frontend/` unless they start with `docs/` or `CLAUDE.md`. SCORE's originals for comparison: `../bid_template/bid_app/frontend/src/openBids.ts`, `components/BidTabs.tsx`, `openBids.test.ts`, `components/BidTabs.test.tsx`, `test-setup.ts`.
- **No backend change at all.** Nothing under `backend/` is touched.
- **Store contract (spec §4):** `export interface OpenRequest { id; number; title; mode: 'view' | 'edit'; step; seq }`, `MAX_OPEN_REQUESTS = 8`, `storageKey(userId) = \`capri_open_requests:${userId}\``, `readOpenRequests`, `useOpenRequests`, `touchOpenRequest(userId, Omit<OpenRequest,'step'|'seq'>)`, `setOpenRequestStep`, `closeOpenRequest`. **No `replaceOpenRequest`.** `touch` on an existing tab spreads the stored tab first (keeps `step`), then overwrites `number`, `title`, `mode`, `seq`. On-screen order is insertion order and never changes; `seq` is eviction bookkeeping only. A corrupt or non-list stored value reads as `[]`; a `localStorage` write failure is swallowed.
- **Label:** `number` is `CapexRequestData.number`; `title` is `CapexRequestData.description ?? ''`. When `title` is empty the strip shows the number alone (no invented text).
- **Active tab comes from the URL only:** `const REQUEST_PATH = /^\/requests\/([^/]+)(?:\/edit)?$/`, and the captured id `new` is treated as no match (`/requests/new` has no tab yet).
- **Tab click navigates by mode:** `mode === 'edit' ? /requests/:id/edit : /requests/:id`. Closing the current tab goes to the tab to its right, else its left, else `/requests`. Closing any other tab does not navigate. **No confirm dialog on close.** The trailing `+` (`aria-label="New request"`) goes to `/requests/new`.
- **Styling:** SCORE's classes verbatim — strip `flex min-w-0 items-stretch gap-1 overflow-x-auto border-b border-border bg-surface-2 px-3`, pills `rounded-md border` with current `border-accent bg-accent` + `font-bold text-accent-fg` + `aria-current="page"`, others `border-border bg-surface` + `font-medium text-muted hover:text-fg`; close control `aria-label="Close <number>"`. Close glyph is `lucide-react`'s `X` at size 14 (CAPRI uses lucide for non-nav glyphs).
- **Strip mounts in `AppShell` between `<header>` and `<main>`, only when `user` is loaded, and renders `null` when no tab is open.** The sidebar nav is unchanged.
- **Wizard step lives on the tab** (spec §3.2): `WizardPage` reads `tabs.find(t => t.id === id)?.step`, falling back to `location.state.step` for the new-request redirect, and writes through `setOpenRequestStep`. A brand-new request (no id) keeps a local step until its first save.
- **Frontend tooling through node** (the repo path contains `&`), run from `frontend/`: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `node ./node_modules/vitest/vitest.mjs run [file]`, `node ./node_modules/vite/bin/vite.js build`.
- **Tests** start with `// @vitest-environment jsdom` and `import '@testing-library/jest-dom/vitest'` (vitest's default environment here is `node`). `fireEvent`, not user-event. Every test file that touches the store calls `localStorage.clear()` in `beforeEach`.
- **Commits:** small, one per task, prefixed like the log: `feat(tabs): …`, `test(tabs): …`, `docs: …`.

## File Structure

**Create:**
- `src/test-setup.ts` — in-memory `Storage` shim for Node ≥ 22 (SCORE's, verbatim) + `jest-dom/vitest` import.
- `src/openRequests.ts` — the store.
- `src/openRequests.test.ts` — 14 store tests.
- `src/components/RequestTabs.tsx` — the strip.
- `src/components/RequestTabs.test.tsx` — 12 strip tests.

**Modify:**
- `vite.config.ts` — `test.setupFiles: ['./src/test-setup.ts']`.
- `src/components/AppShell.tsx` — mount `<RequestTabs userId={user.id} />`.
- `src/routes/WizardPage.tsx` — step from the tab; `touch` on load (`mode: 'edit'`); unavailable branch.
- `src/routes/WizardPage.test.tsx` — `localStorage.clear()`, six tab tests including the mid-mount switch.
- `src/routes/RequestDetailPage.tsx` — `touch` on load (`mode: 'view'`); unavailable branch.
- `src/routes/RequestDetailPage.test.tsx` — `localStorage.clear()`, two tab tests.
- `CLAUDE.md` — Frontend layout bullets + an "Open-request tabs" section.

**Untouched:** `src/routes/RequestsListPage.tsx` (no delete action exists to close a tab from), everything under `backend/`.

---

### Task 1: Test setup shim and the open-request store

**Files:**
- Create: `src/test-setup.ts`
- Modify: `vite.config.ts`
- Create: `src/openRequests.ts`
- Test: `src/openRequests.test.ts`

**Interfaces:**
- Produces: everything in the Global Constraints "Store contract" line, importable from `'../openRequests'` (components/routes) or `'./openRequests'` (src root).

- [ ] **Step 1: Install the localStorage shim**

Node 26 ships an inert `globalThis.localStorage` that jsdom does not replace, so every storage test would find a dead stub. Create `src/test-setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'

/* Node >= 22 ships an EXPERIMENTAL globalThis.localStorage that is undefined
   unless node is started with --localstorage-file, and vitest's jsdom
   environment does not overwrite an existing global. Under a new-enough node
   every test touching localStorage therefore finds node's dead stub instead of
   a working one. jsdom's own implementation is not reachable either, because
   vitest's `window` IS `globalThis`, so the fix is a plain in-memory Storage.
   (Ported from SCORE's test-setup.ts, which hit this on node 26.) */
class MemoryStorage implements Storage {
  private map = new Map<string, string>()
  get length() { return this.map.size }
  clear() { this.map.clear() }
  getItem(key: string) { return this.map.get(key) ?? null }
  key(index: number) { return [...this.map.keys()][index] ?? null }
  removeItem(key: string) { this.map.delete(key) }
  setItem(key: string, value: string) { this.map.set(key, String(value)) }
}

for (const name of ['localStorage', 'sessionStorage'] as const) {
  if (typeof globalThis[name]?.clear !== 'function') {
    Object.defineProperty(globalThis, name, {
      value: new MemoryStorage(),
      configurable: true,
      writable: true,
    })
  }
}
```

In `vite.config.ts`, add `setupFiles` to the `test` block (leave `environment: 'node'` — individual test files opt into jsdom):

```ts
  test: {
    environment: 'node',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
```

- [ ] **Step 2: Write the failing store tests**

Create `src/openRequests.test.ts`:

```ts
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { beforeEach, describe, expect, it } from 'vitest'
import {
  MAX_OPEN_REQUESTS,
  closeOpenRequest,
  readOpenRequests,
  setOpenRequestStep,
  storageKey,
  touchOpenRequest,
} from './openRequests'

const ME = 'u1'

function tab(id: string, mode: 'view' | 'edit' = 'edit') {
  return { id, number: `CX${id}`, title: `Forklift ${id}`, mode }
}

beforeEach(() => {
  localStorage.clear()
})

describe('the open-request set', () => {
  it('is empty before anything is opened', () => {
    expect(readOpenRequests(ME)).toEqual([])
  })

  it('remembers a request that was opened', () => {
    touchOpenRequest(ME, tab('a'))

    expect(readOpenRequests(ME)).toMatchObject([
      { id: 'a', number: 'CXa', title: 'Forklift a', mode: 'edit', step: 0 },
    ])
  })

  it('does not duplicate a request that is opened twice', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest(ME, tab('a'))

    expect(readOpenRequests(ME)).toHaveLength(1)
  })

  it('refreshes a stale label when the request is opened again', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest(ME, { ...tab('a'), title: 'Renamed forklift' })

    expect(readOpenRequests(ME)[0].title).toBe('Renamed forklift')
  })

  it('leaves a reopened request where it sits in the strip', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest(ME, tab('b'))
    touchOpenRequest(ME, tab('c'))
    touchOpenRequest(ME, tab('a'))

    // Tabs that jump to the end on every click are unusable to aim at.
    expect(readOpenRequests(ME).map((t) => t.id)).toEqual(['a', 'b', 'c'])
  })

  it('reopening in the other mode updates the mode and keeps the step', () => {
    touchOpenRequest(ME, tab('a', 'edit'))
    setOpenRequestStep(ME, 'a', 3)

    touchOpenRequest(ME, tab('a', 'view'))

    expect(readOpenRequests(ME)[0]).toMatchObject({ mode: 'view', step: 3 })
  })
})

describe('per-tab step memory', () => {
  it('remembers which step each request was left on', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest(ME, tab('b'))

    setOpenRequestStep(ME, 'a', 3)

    const byId = Object.fromEntries(readOpenRequests(ME).map((t) => [t.id, t.step]))
    expect(byId).toEqual({ a: 3, b: 0 })
  })

  it('keeps the remembered step when the request is reopened', () => {
    touchOpenRequest(ME, tab('a'))
    setOpenRequestStep(ME, 'a', 2)

    touchOpenRequest(ME, tab('a'))

    expect(readOpenRequests(ME)[0].step).toBe(2)
  })

  it('ignores a step for a request that is not open', () => {
    touchOpenRequest(ME, tab('a'))

    setOpenRequestStep(ME, 'ghost', 4)

    expect(readOpenRequests(ME).map((t) => t.id)).toEqual(['a'])
  })
})

describe('closing a tab', () => {
  it('removes only the request that was closed', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest(ME, tab('b'))

    closeOpenRequest(ME, 'a')

    expect(readOpenRequests(ME).map((t) => t.id)).toEqual(['b'])
  })
})

describe('the cap', () => {
  it('evicts the least recently opened request past the cap', () => {
    for (let i = 0; i < MAX_OPEN_REQUESTS; i++) touchOpenRequest(ME, tab(String(i)))
    // Re-open the oldest, so it is no longer the least recently seen.
    touchOpenRequest(ME, tab('0'))

    touchOpenRequest(ME, tab('new'))

    const ids = readOpenRequests(ME).map((t) => t.id)
    expect(ids).toHaveLength(MAX_OPEN_REQUESTS)
    expect(ids).toContain('0')
    expect(ids).not.toContain('1')
  })
})

describe('storage', () => {
  it('keeps one user’s tabs out of another’s', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest('u2', tab('b'))

    expect(readOpenRequests(ME).map((t) => t.id)).toEqual(['a'])
    expect(readOpenRequests('u2').map((t) => t.id)).toEqual(['b'])
  })

  it('falls back to empty when the stored value is corrupt', () => {
    localStorage.setItem(storageKey(ME), '{not json')

    expect(readOpenRequests(ME)).toEqual([])
  })

  it('falls back to empty when the stored value is not a list of tabs', () => {
    localStorage.setItem(storageKey(ME), '{"id":"a"}')

    expect(readOpenRequests(ME)).toEqual([])
  })
})
```

- [ ] **Step 3: Run to verify it fails**

Run: `node ./node_modules/vitest/vitest.mjs run src/openRequests.test.ts`
Expected: FAIL — cannot resolve `./openRequests`.

- [ ] **Step 4: Write the store**

Create `src/openRequests.ts` (SCORE's `openBids.ts` renamed, `mode` added, `replaceOpenBid` dropped; the comments say why and stay):

```ts
/* The set of CAPEX requests a person has open at once, kept in localStorage.
 *
 * Nothing here is unsaved -- the wizard persists every save server-side and the
 * detail page is read-only -- so a tab is only ever a pointer plus enough label
 * to render it. Ids alone would mean one request per tab on every page load,
 * which an app-wide strip cannot afford, so each tab carries a label snapshot
 * and the page that loads the request refreshes its own.
 *
 * Ported from SCORE's openBids.ts (bid_template/bid_app). CAPRI adds `mode`
 * because a request has two pages (view and edit) where a bid has one, and
 * drops replaceOpenBid because a request keeps one id for its life.
 */

import { useEffect, useState } from 'react'

export interface OpenRequest {
  id: string
  number: string        // "CX000123"
  title: string         // the request's description, truncated by CSS not here
  /* Which page the person was on, so switching tabs never throws an approver
     into edit mode. */
  mode: 'view' | 'edit'
  /* Which wizard step this request was left on; 0 for a view-only tab. */
  step: number
  /* Bookkeeping only: a monotonic stamp of when this tab was last opened, so the
     cap evicts the least recently seen. On-screen order is insertion order and
     deliberately never changes -- tabs that jump on click cannot be aimed at. */
  seq: number
}

/* Several at once is the use case; eight should never be felt. */
export const MAX_OPEN_REQUESTS = 8

/* Keyed by user: localStorage is per browser, not per account, and two people
   sharing a machine must not inherit each other's tabs. */
export function storageKey(userId: string): string {
  return `capri_open_requests:${userId}`
}

function isOpenRequest(value: unknown): value is OpenRequest {
  const t = value as Partial<OpenRequest> | null
  return (
    typeof t === 'object' &&
    t !== null &&
    typeof t.id === 'string' &&
    typeof t.number === 'string' &&
    typeof t.title === 'string' &&
    (t.mode === 'view' || t.mode === 'edit') &&
    typeof t.step === 'number' &&
    typeof t.seq === 'number'
  )
}

export function readOpenRequests(userId: string): OpenRequest[] {
  try {
    const raw = localStorage.getItem(storageKey(userId))
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter(isOpenRequest) : []
  } catch {
    return []
  }
}

/* The strip and the pages both write here, and neither owns the other, so the
   store notifies rather than being lifted into a provider. `useOpenRequests` is
   the only subscriber shape needed -- there is no snapshot identity to get
   wrong, because each listener re-reads for itself. */
const listeners = new Set<() => void>()

function write(userId: string, tabs: OpenRequest[]): OpenRequest[] {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(tabs))
  } catch {
    /* private mode: the strip still works for this session */
  }
  listeners.forEach((notify) => notify())
  return tabs
}

export function useOpenRequests(userId: string): OpenRequest[] {
  const [tabs, setTabs] = useState(() => readOpenRequests(userId))

  useEffect(() => {
    const resync = () => setTabs(readOpenRequests(userId))
    listeners.add(resync)
    resync()
    return () => {
      listeners.delete(resync)
    }
  }, [userId])

  return tabs
}

/* Add the request, or refresh the label and mode of the one already there.
   Called whenever a request page loads, which is every entry point -- the list,
   the dashboard, an email deep link, the new-request redirect -- because all of
   them route through the same two URLs. */
export function touchOpenRequest(
  userId: string,
  req: Omit<OpenRequest, 'step' | 'seq'>,
): OpenRequest[] {
  const tabs = readOpenRequests(userId)
  const seq = Math.max(0, ...tabs.map((t) => t.seq)) + 1
  const at = tabs.findIndex((t) => t.id === req.id)

  if (at >= 0) {
    const next = tabs.slice()
    // Spreading the existing tab first keeps its remembered step.
    next[at] = { ...next[at], ...req, seq }
    return write(userId, next)
  }

  let next = [...tabs, { ...req, step: 0, seq }]
  if (next.length > MAX_OPEN_REQUESTS) {
    const oldest = next.reduce((a, b) => (a.seq <= b.seq ? a : b))
    next = next.filter((t) => t !== oldest)
  }
  return write(userId, next)
}

export function setOpenRequestStep(
  userId: string,
  id: string,
  step: number,
): OpenRequest[] {
  const tabs = readOpenRequests(userId)
  if (!tabs.some((t) => t.id === id)) return tabs
  return write(
    userId,
    tabs.map((t) => (t.id === id ? { ...t, step } : t)),
  )
}

export function closeOpenRequest(userId: string, id: string): OpenRequest[] {
  return write(
    userId,
    readOpenRequests(userId).filter((t) => t.id !== id),
  )
}
```

- [ ] **Step 5: Run the store tests**

Run: `node ./node_modules/vitest/vitest.mjs run src/openRequests.test.ts`
Expected: 14 passed. If every test fails with `localStorage.clear is not a function`, the shim is not wired — re-check `setupFiles` in `vite.config.ts`.

- [ ] **Step 6: Typecheck and run the whole frontend suite**

Run: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, then `node ./node_modules/vitest/vitest.mjs run`.
Expected: tsc clean; 166 previous + 14 new = 180 passed (the two pre-existing `RequestSectionsPage.test.tsx` stderr warnings are known).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/test-setup.ts frontend/vite.config.ts frontend/src/openRequests.ts frontend/src/openRequests.test.ts
git commit -m "feat(tabs): open-request store in localStorage, per user, with a Node 26 storage shim for tests"
```

---

### Task 2: The tab strip, mounted in the shell

**Files:**
- Create: `src/components/RequestTabs.tsx`
- Create: `src/components/RequestTabs.test.tsx`
- Modify: `src/components/AppShell.tsx`

**Interfaces:**
- Consumes: `useOpenRequests`, `closeOpenRequest`, `touchOpenRequest`, type `OpenRequest` (Task 1).
- Produces: `RequestTabs({ userId }: { userId: string })`, `data-testid="request-tabs"`.

- [ ] **Step 1: Write the failing strip tests**

Create `src/components/RequestTabs.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { RequestTabs } from './RequestTabs'
import { touchOpenRequest } from '../openRequests'

const ME = 'u1'

function open(id: string, number: string, title: string, mode: 'view' | 'edit' = 'view') {
  touchOpenRequest(ME, { id, number, title, mode })
}

function Where() {
  return <span data-testid="where">{useLocation().pathname}</span>
}

function renderTabs(at: string) {
  return render(
    <MemoryRouter initialEntries={[at]}>
      <RequestTabs userId={ME} />
      <Where />
      <Routes>
        <Route path="*" element={null} />
      </Routes>
    </MemoryRouter>,
  )
}

const click = (name: RegExp | string) =>
  fireEvent.click(screen.getByRole('button', { name }))

beforeEach(() => {
  localStorage.clear()
})

describe('the request tab strip', () => {
  it('renders nothing at all when no request is open', () => {
    const { container } = renderTabs('/')

    // A first-time user must see today's app, not an empty bar.
    expect(container.querySelector('[data-testid="request-tabs"]')).toBeNull()
  })

  it('shows a tab for each open request, naming the number and the title', () => {
    open('a', 'CX000142', 'Forklift')
    open('b', 'CX000151', 'Tank monitor')

    renderTabs('/requests/a')

    expect(screen.getByRole('button', { name: /^CX000142/ })).toHaveTextContent('Forklift')
    expect(screen.getByRole('button', { name: /^CX000151/ })).toBeInTheDocument()
  })

  it('shows the number alone when the request has no description', () => {
    open('a', 'CX000142', '')

    renderTabs('/requests/a')

    const tab = screen.getByRole('button', { name: /^CX000142/ })
    expect(tab).toHaveTextContent(/^CX000142$/)
    expect(tab).toHaveAttribute('title', 'CX000142')
  })

  it('marks the request in the address bar as the current tab', () => {
    open('a', 'CX000142', 'Forklift')
    open('b', 'CX000151', 'Tank monitor')

    renderTabs('/requests/b')

    // Never colour alone: the marker has to be readable by assistive tech too.
    expect(screen.getByRole('button', { name: /^CX000151/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: /^CX000142/ })).not.toHaveAttribute('aria-current')
  })

  it('marks the same tab current on the edit page as on the view page', () => {
    open('a', 'CX000142', 'Forklift')

    renderTabs('/requests/a/edit')

    expect(screen.getByRole('button', { name: /^CX000142/ })).toHaveAttribute('aria-current', 'page')
  })

  it('marks no tab as current when the page is not a request', () => {
    open('a', 'CX000142', 'Forklift')

    renderTabs('/messages')

    expect(screen.getByRole('button', { name: /^CX000142/ })).not.toHaveAttribute('aria-current')
  })

  it('marks no tab as current on the new-request page', () => {
    open('new', 'CX000000', 'Not a real tab')

    renderTabs('/requests/new')

    expect(screen.getByRole('button', { name: /^CX000000/ })).not.toHaveAttribute('aria-current')
  })

  it('opens a view tab on the detail page and an edit tab in the wizard', () => {
    open('a', 'CX000142', 'Forklift', 'view')
    open('b', 'CX000151', 'Tank monitor', 'edit')
    renderTabs('/messages')

    click(/^CX000142/)
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/requests\/a$/)

    click(/^CX000151/)
    expect(screen.getByTestId('where')).toHaveTextContent('/requests/b/edit')
  })

  it('closes a tab without leaving the page you are on', () => {
    open('a', 'CX000142', 'Forklift')
    open('b', 'CX000151', 'Tank monitor')
    renderTabs('/requests/a')

    click(/Close CX000151/)

    expect(screen.queryByRole('button', { name: /^CX000151/ })).not.toBeInTheDocument()
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/requests\/a$/)
  })

  it('moves to a neighbouring request when the open one is closed', () => {
    open('a', 'CX000142', 'Forklift', 'edit')
    open('b', 'CX000151', 'Tank monitor')
    renderTabs('/requests/b')

    click(/Close CX000151/)

    // The neighbour opens in ITS remembered mode.
    expect(screen.getByTestId('where')).toHaveTextContent('/requests/a/edit')
  })

  it('falls back to the requests list when the last tab is closed', () => {
    open('a', 'CX000142', 'Forklift')
    renderTabs('/requests/a')

    click(/Close CX000142/)

    expect(screen.getByTestId('where')).toHaveTextContent(/^\/requests$/)
  })

  it('starts a new request from the trailing control', () => {
    open('a', 'CX000142', 'Forklift')
    renderTabs('/requests/a')

    click('New request')

    expect(screen.getByTestId('where')).toHaveTextContent('/requests/new')
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/RequestTabs.test.tsx`
Expected: FAIL — cannot resolve `./RequestTabs`.

- [ ] **Step 3: Write the strip**

Create `src/components/RequestTabs.tsx`:

```tsx
import { useLocation, useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import { closeOpenRequest, useOpenRequests, type OpenRequest } from '../openRequests'

/* The request currently on screen, from the URL rather than from stored state:
   the address bar is the one place that cannot drift out of step with what is
   rendered. Both request pages count -- /requests/:id (view) and
   /requests/:id/edit (wizard) -- and /requests/new does not: a request with no
   id yet has no tab. */
const REQUEST_PATH = /^\/requests\/([^/]+)(?:\/edit)?$/

function activeRequestId(pathname: string): string | null {
  const id = REQUEST_PATH.exec(pathname)?.[1] ?? null
  return id === 'new' ? null : id
}

/* A tab remembers which page the person was on. */
function pathFor(tab: OpenRequest): string {
  return tab.mode === 'edit' ? `/requests/${tab.id}/edit` : `/requests/${tab.id}`
}

/* Where to go when the tab you are looking at is the one being closed: the tab
   to its right, else the one to its left, else nothing is left to show. */
function neighbourOf(tabs: OpenRequest[], id: string): OpenRequest | null {
  const at = tabs.findIndex((t) => t.id === id)
  if (at < 0) return null
  return tabs[at + 1] ?? tabs[at - 1] ?? null
}

export function RequestTabs({ userId }: { userId: string }) {
  const tabs = useOpenRequests(userId)
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const active = activeRequestId(pathname)

  // Nothing open means no strip at all, not an empty bar.
  if (tabs.length === 0) return null

  function close(tab: OpenRequest) {
    closeOpenRequest(userId, tab.id)
    if (tab.id !== active) return
    const next = neighbourOf(tabs, tab.id)
    navigate(next ? pathFor(next) : '/requests')
  }

  return (
    <div
      data-testid="request-tabs"
      className="flex min-w-0 items-stretch gap-1 overflow-x-auto border-b border-border bg-surface-2 px-3"
    >
      {tabs.map((tab) => {
        const current = tab.id === active
        return (
          /* Outlined pills, the current one FILLED in the accent: every tab
             carries a visible border, and the active one reads at a glance.
             bg-accent + text-accent-fg is the same active treatment the
             sidebar pill uses. */
          <span
            key={tab.id}
            className={`my-1 flex min-w-0 shrink-0 items-center rounded-md border ${
              current ? 'border-accent bg-accent' : 'border-border bg-surface'
            }`}
          >
            <button
              type="button"
              // Weight and the filled outline as well as colour -- never colour alone.
              aria-current={current ? 'page' : undefined}
              onClick={() => navigate(pathFor(tab))}
              className={`flex min-w-0 max-w-56 items-baseline gap-2 py-1.5 pl-2 pr-1 text-sm ${
                current
                  ? 'font-bold text-accent-fg'
                  : 'font-medium text-muted hover:text-fg'
              }`}
              title={tab.title ? `${tab.number} — ${tab.title}` : tab.number}
            >
              <span className="shrink-0">{tab.number}</span>
              {tab.title && (
                <span
                  className={`min-w-0 truncate text-xs ${
                    current ? 'text-accent-fg/80' : 'text-muted'
                  }`}
                >
                  {tab.title}
                </span>
              )}
            </button>
            <button
              type="button"
              aria-label={`Close ${tab.number}`}
              onClick={() => close(tab)}
              className={`mr-1 rounded p-1 ${
                current
                  ? 'text-accent-fg/80 hover:bg-white/20 hover:text-accent-fg'
                  : 'text-muted hover:bg-surface-2 hover:text-fg'
              }`}
            >
              <X size={14} />
            </button>
          </span>
        )
      })}
      <button
        type="button"
        aria-label="New request"
        onClick={() => navigate('/requests/new')}
        className="shrink-0 px-2 text-lg font-semibold leading-none text-muted hover:text-fg"
      >
        +
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Run the strip tests**

Run: `node ./node_modules/vitest/vitest.mjs run src/components/RequestTabs.test.tsx`
Expected: 12 passed.

- [ ] **Step 5: Mount the strip in the shell**

In `src/components/AppShell.tsx`: add `import { RequestTabs } from './RequestTabs'` after the `PingPanel` import. Between the closing `</header>` and `<main …>` insert:

```tsx
        {user && <RequestTabs userId={user.id} />}
```

- [ ] **Step 6: Typecheck, run all tests, build**

Run: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `node ./node_modules/vitest/vitest.mjs run`, `node ./node_modules/vite/bin/vite.js build`.
Expected: tsc clean; 180 + 12 = 192 passed; build succeeds. (Nothing calls `touch` yet, so the strip is still invisible in the app — that lands in Tasks 3–4.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/RequestTabs.tsx frontend/src/components/RequestTabs.test.tsx frontend/src/components/AppShell.tsx
git commit -m "feat(tabs): request tab strip in the app shell, active tab from the URL, opens by mode"
```

---

### Task 3: The wizard — step on the tab, touch on load, unavailable branch

**Files:**
- Modify: `src/routes/WizardPage.tsx`
- Modify: `src/routes/WizardPage.test.tsx`

**Interfaces:**
- Consumes: `readOpenRequests`, `useOpenRequests`, `touchOpenRequest`, `setOpenRequestStep`, `closeOpenRequest` (Task 1).
- Produces: nothing new; behaviour only.

Background for the implementer: `WizardPage` currently keeps `step` in `useState` seeded from `location.state` (line 41). React Router keeps this component mounted when only `:id` changes, so that local step carries request A's step onto request B — the bug spec §3.2 describes. The step moves onto the tab. A brand-new request (`/requests/new`, no id) has no tab until its first save redirects to `/requests/:id/edit` with `state: { step }`, so it keeps a local step until then, and the redirect's step is seeded into the tab the moment it is created.

- [ ] **Step 1: Write the failing tests**

In `src/routes/WizardPage.test.tsx`:

Add to the imports at the top (keep the existing ones):

```tsx
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { ApiError } from '../api/client'
import { readOpenRequests, setOpenRequestStep, touchOpenRequest } from '../openRequests'
```

(Replace the existing `import { MemoryRouter, Routes, Route } from 'react-router-dom'` line with the one above.)

Change `renderAt` to accept extra children rendered inside the router, and clear storage before every test in the file (the store now persists step across tests that share user `me` and request `req-1`):

```tsx
function renderAt(path: string, extra?: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        {extra}
        <Routes>
          <Route path="/requests/new" element={<WizardPage />} />
          <Route path="/requests/:id/edit" element={<WizardPage />} />
          <Route path="/requests/:id" element={<div>Detail</div>} />
          <Route path="/requests" element={<div>List</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function Switcher({ to }: { to: string }) {
  const navigate = useNavigate()
  return <button type="button" onClick={() => navigate(to)}>switch</button>
}

beforeEach(() => {
  localStorage.clear()
})
```

Put the top-level `beforeEach` directly after `Switcher`, before the first `describe`. Then append a new `describe` at the end of the file:

```tsx
describe('WizardPage and the open-request set', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRequest).mockResolvedValue(makeRequest('DRAFT'))
  })

  const currentStep = () =>
    screen.getAllByRole('button', { current: 'step' })[0]

  it('opens an edit tab for the request it loaded', async () => {
    renderAt('/requests/req-1/edit')
    await screen.findByText('Request CX000042')

    expect(readOpenRequests('me')).toMatchObject([
      { id: 'req-1', number: 'CX000042', title: 'Forklift', mode: 'edit', step: 0 },
    ])
  })

  it('reopens the request on the step it was left on', async () => {
    touchOpenRequest('me', { id: 'req-1', number: 'CX000042', title: 'Forklift', mode: 'edit' })
    setOpenRequestStep('me', 'req-1', 2)

    renderAt('/requests/req-1/edit')
    await screen.findByText('Request CX000042')

    expect(currentStep()).toHaveTextContent('Effect on Ops')
  })

  it('remembers the step when you move through the wizard', async () => {
    renderAt('/requests/req-1/edit')
    await screen.findByText('Request CX000042')

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(readOpenRequests('me')[0].step).toBe(1))
    expect(currentStep()).toHaveTextContent('Description')
  })

  it('keeps each request on its own step when you switch between tabs', async () => {
    touchOpenRequest('me', { id: 'a', number: 'CX000001', title: 'One', mode: 'edit' })
    setOpenRequestStep('me', 'a', 2)
    touchOpenRequest('me', { id: 'b', number: 'CX000002', title: 'Two', mode: 'edit' })
    vi.mocked(getRequest).mockImplementation(async (id: string) => ({
      ...makeRequest('DRAFT'), id,
      number: id === 'a' ? 'CX000001' : 'CX000002',
      description: id === 'a' ? 'One' : 'Two',
    }))

    renderAt('/requests/a/edit', <Switcher to="/requests/b/edit" />)
    await screen.findByText('Request CX000001')
    expect(currentStep()).toHaveTextContent('Effect on Ops')

    // Same route component, changed param -- local step state would carry
    // request a's step across and land b on Effect on Ops, and a form seeded
    // once for a would show (and save!) a's fields as b's.
    fireEvent.click(screen.getByRole('button', { name: 'switch' }))

    await screen.findByText('Request CX000002')
    expect(currentStep()).toHaveTextContent('Basic Info')
    expect(await screen.findByDisplayValue('Two')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('One')).toBeNull()
  })

  it('carries a new request’s step into its tab across the first-save redirect', async () => {
    vi.mocked(getRequest).mockResolvedValue({ ...makeRequest('DRAFT'), id: 'new-1' })
    renderAt('/requests/new')
    await screen.findByText('New Request')

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(currentStep()).toHaveTextContent('Description')
    fireEvent.click(screen.getByRole('button', { name: 'Save Draft' }))

    await waitFor(() => expect(readOpenRequests('me')).toMatchObject([{ id: 'new-1', step: 1 }]))
    expect(currentStep()).toHaveTextContent('Description')
  })

  it('offers to close the tab when the request cannot be loaded', async () => {
    touchOpenRequest('me', { id: 'req-1', number: 'CX000042', title: 'Gone', mode: 'edit' })
    vi.mocked(getRequest).mockRejectedValue(new ApiError(404, 'Request not found.'))

    renderAt('/requests/req-1/edit')

    // Without this the route shows "Loading…" forever -- and a stored tab is
    // exactly how a request that no longer exists gets opened.
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not be loaded/i)
    fireEvent.click(screen.getByRole('button', { name: /Close this tab/ }))

    expect(readOpenRequests('me')).toEqual([])
    expect(await screen.findByText('List')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify the right tests fail**

Run: `node ./node_modules/vitest/vitest.mjs run src/routes/WizardPage.test.tsx`
Expected: the six new tests FAIL. In particular `keeps each request on its own step when you switch between tabs` must fail with the current step reading **Effect on Ops** after the switch — that is the `useState` bug reproduced (and, once the step assertion is made to pass alone, the `findByDisplayValue('Two')` assertion would still fail: the form seeded once for `a` is never reseeded for `b`). `offers to close the tab…` fails on a missing alert. All 22 pre-existing tests still pass.

- [ ] **Step 3: Move the step onto the tab and touch on load**

In `src/routes/WizardPage.tsx`:

Add the import after the `budgetAmountError` import:

```tsx
import {
  readOpenRequests, useOpenRequests, touchOpenRequest, setOpenRequestStep, closeOpenRequest,
} from '../openRequests'
```

Change the request query to expose the error state:

```tsx
  const { data, isError } = useQuery({
    queryKey: ['request', routeId],
    queryFn: () => getRequest(routeId!),
    enabled: !!routeId,
  })
```

Replace the line `const [step, setStep] = useState<number>((location.state as { step?: number } | null)?.step ?? 0)` with:

```tsx
  // The step lives on the tab (openRequests.ts), so switching tabs lands where
  // you were. React Router keeps this component mounted when only :id changes,
  // so a useState step would carry request A's step onto request B. A brand-new
  // request has no tab until its first save redirects here with an id, so it
  // keeps a local step until then; the redirect passes that step in
  // location.state and the load effect below seeds it into the new tab.
  const userId = me?.id ?? null
  const tabs = useOpenRequests(userId ?? '')
  const initialStep = (location.state as { step?: number } | null)?.step ?? 0
  const [newStep, setNewStep] = useState<number>(initialStep)
  const step = routeId ? (tabs.find((t) => t.id === routeId)?.step ?? initialStep) : newStep
  const setStep = (next: number) => {
    if (routeId && userId) setOpenRequestStep(userId, routeId, next)
    else setNewStep(next)
  }
```

Replace the "Seed the form once" `useEffect` (the one with `if (form) return`) with one that also **reseeds when the route id changes**. The tab strip switches `:id` under a mounted `WizardPage`, and a form seeded for request A must never be shown as — or saved into — request B. `useRef` is already imported:

```tsx
  // Seed the form from the loaded draft (edit) or a blank form (new), and
  // reseed whenever the route id changes: the tab strip switches :id under a
  // mounted WizardPage, and a form seeded for request A must never be shown
  // as -- or saved into -- request B. The ref, not `data`, decides: a refetch
  // of the same request must not wipe unsaved edits.
  const seededFor = useRef<string | null>(null)
  useEffect(() => {
    if (routeId) {
      if (data && seededFor.current !== routeId) {
        setForm(toForm(data))
        setBudgetError(null)
        seededFor.current = routeId
      }
    } else if (me && !form) {
      setForm(blankForm(me.division_id ?? '', today()))
    }
  }, [routeId, data, me, form])
```

Directly after that effect, add the touch effect. It depends on primitive fields, not the object, so a refetch that returns an equal request does not re-touch and bump `seq`:

```tsx
  // One hook point covers every way in -- the list, the dashboard, an email deep
  // link, the new-request redirect -- because all of them route here.
  const loadedId = data?.id
  const loadedNumber = data?.number
  const loadedTitle = data?.description ?? ''
  useEffect(() => {
    if (!userId || !loadedId || !loadedNumber) return
    const isNewTab = !readOpenRequests(userId).some((t) => t.id === loadedId)
    touchOpenRequest(userId, { id: loadedId, number: loadedNumber, title: loadedTitle, mode: 'edit' })
    // A tab created just now starts at step 0; the new-request redirect carried
    // the step the person was on, so seed it once.
    if (isNewTab && initialStep) setOpenRequestStep(userId, loadedId, initialStep)
  }, [userId, loadedId, loadedNumber, loadedTitle, initialStep])
```

Directly before `if (!form || !hidden) return <p className="text-sm text-muted">Loading…</p>`, add the unavailable branch:

```tsx
  // A stored tab is exactly how a request that no longer exists gets opened;
  // without this branch the page would show "Loading…" forever.
  if (routeId && isError) {
    return (
      <div className="max-w-3xl">
        <BrandCard title="Request unavailable" subtitle={routeId} mark="newRequest">
          <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">
            This request could not be loaded. It may have been deleted, or you may no longer have access to it.
          </p>
          <Button variant="secondary" onClick={() => {
            if (userId) closeOpenRequest(userId, routeId)
            navigate('/requests')
          }}>
            Close this tab
          </Button>
        </BrandCard>
      </div>
    )
  }
```

Nothing else changes: `goToStep`, the Back button's `setStep(at - 1)`, `clampStep(step, sections.length)` and the two `navigate(…, { state: { step } })` redirects keep working against the new `step`/`setStep`.

- [ ] **Step 4: Run the wizard tests**

Run: `node ./node_modules/vitest/vitest.mjs run src/routes/WizardPage.test.tsx`
Expected: 28 passed (22 + 6). If `carries a new request’s step…` fails with step 0, check that the touch effect reads `readOpenRequests` **before** calling `touchOpenRequest` and that `initialStep` is in its dependency list.

- [ ] **Step 5: Typecheck, run all tests, commit**

Run: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` and `node ./node_modules/vitest/vitest.mjs run`.
Expected: tsc clean (`useState` is still used for `newStep`, so no unused-import error); 192 + 6 = 198 passed.

```bash
git add frontend/src/routes/WizardPage.tsx frontend/src/routes/WizardPage.test.tsx
git commit -m "feat(tabs): wizard keeps its step on the tab, opens an edit tab on load, closes a tab it cannot load"
```

---

### Task 4: The detail page — touch on load, unavailable branch

**Files:**
- Modify: `src/routes/RequestDetailPage.tsx`
- Modify: `src/routes/RequestDetailPage.test.tsx`

**Interfaces:**
- Consumes: `touchOpenRequest`, `closeOpenRequest` (Task 1).

- [ ] **Step 1: Write the failing tests**

In `src/routes/RequestDetailPage.test.tsx`, add to the imports:

```tsx
import { ApiError } from '../api/client'
import { readOpenRequests, touchOpenRequest } from '../openRequests'
```

Extend `renderPage` with a list route so the close button has somewhere to go:

```tsx
function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/requests/req-1']}>
        <Routes>
          <Route path="/requests/:id" element={<RequestDetailPage />} />
          <Route path="/requests" element={<div>List</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
```

Add a top-level `beforeEach(() => { localStorage.clear() })` right after `renderPage`. Then append a new `describe` at the end of the file:

```tsx
describe('RequestDetailPage and the open-request set', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRoles = ['APPROVER']
  })

  it('opens a view tab for the request it loaded', async () => {
    vi.mocked(getRequest).mockResolvedValue(makeRequest())
    renderPage()
    await screen.findByText('Request CX000042')

    expect(readOpenRequests('approver-1')).toMatchObject([
      { id: 'req-1', number: 'CX000042', title: 'Forklift', mode: 'view', step: 0 },
    ])
  })

  it('offers to close the tab when the request cannot be loaded', async () => {
    touchOpenRequest('approver-1', { id: 'req-1', number: 'CX000042', title: 'Gone', mode: 'view' })
    vi.mocked(getRequest).mockRejectedValue(new ApiError(404, 'Request not found.'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not be loaded/i)
    fireEvent.click(screen.getByRole('button', { name: /Close this tab/ }))

    expect(readOpenRequests('approver-1')).toEqual([])
    expect(await screen.findByText('List')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `node ./node_modules/vitest/vitest.mjs run src/routes/RequestDetailPage.test.tsx`
Expected: the two new tests FAIL (empty store; no alert); the existing tests pass.

- [ ] **Step 3: Touch on load and add the unavailable branch**

In `src/routes/RequestDetailPage.tsx`:

Change the first import to `import { useState, useRef, useEffect } from 'react'` and add, after the `PingModal` import:

```tsx
import { touchOpenRequest, closeOpenRequest } from '../openRequests'
```

Change the request query to expose the error state:

```tsx
  const { data: req, isError } = useQuery({ queryKey: ['request', id], queryFn: () => getRequest(id) })
```

Directly after the `fileRef` line (all hooks must run before the early returns), add:

```tsx
  // Register this request in the tab strip. Primitive deps, not the object, so
  // a refetch that returns an equal request does not re-touch and bump seq.
  const userId = me?.id
  const reqId = req?.id
  const reqNumber = req?.number
  const reqTitle = req?.description ?? ''
  useEffect(() => {
    if (!userId || !reqId || !reqNumber) return
    touchOpenRequest(userId, { id: reqId, number: reqNumber, title: reqTitle, mode: 'view' })
  }, [userId, reqId, reqNumber, reqTitle])
```

Directly before `if (!req || !me) return <p className="text-sm text-muted">Loading…</p>`, add:

```tsx
  // A stored tab is exactly how a request that no longer exists gets opened;
  // without this branch the page would show "Loading…" forever.
  if (isError) {
    return (
      <div className="max-w-3xl">
        <BrandCard title="Request unavailable" subtitle={id} mark="requests">
          <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">
            This request could not be loaded. It may have been deleted, or you may no longer have access to it.
          </p>
          <Button variant="secondary" onClick={() => {
            if (me) closeOpenRequest(me.id, id)
            navigate('/requests')
          }}>
            Close this tab
          </Button>
        </BrandCard>
      </div>
    )
  }
```

- [ ] **Step 4: Run the detail tests**

Run: `node ./node_modules/vitest/vitest.mjs run src/routes/RequestDetailPage.test.tsx`
Expected: all pass (previous count + 2).

- [ ] **Step 5: Typecheck, run all tests, build, commit**

Run: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `node ./node_modules/vitest/vitest.mjs run`, `node ./node_modules/vite/bin/vite.js build`.
Expected: tsc clean; 198 + 2 = 200 passed; build succeeds.

```bash
git add frontend/src/routes/RequestDetailPage.tsx frontend/src/routes/RequestDetailPage.test.tsx
git commit -m "feat(tabs): detail page opens a view tab on load and closes a tab it cannot load"
```

---

### Task 5: Entry-path sweep, end-to-end check, docs

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Sweep every way into a request**

Run from `frontend/`:

```bash
grep -rn "navigate(\`/requests/\|to={\`/requests/\|to=\"/requests/\|navigate('/requests/" src --include=*.tsx | grep -v test
```

Expected: every hit resolves to `/requests/new`, `/requests/:id` or `/requests/:id/edit` (RequestsListPage rows, DashboardPage, RequestDetailPage's Edit button, WizardPage's redirects, PingDetail's request chip, AppShell nav, RequestTabs). All of those land on one of the two touching pages or on `/requests/new`, so no further wiring is needed. If any hit points somewhere else, stop and report it — the store has no other hook point.

- [ ] **Step 2: Full gates**

Run from `frontend/`: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `node ./node_modules/vitest/vitest.mjs run`, `node ./node_modules/vite/bin/vite.js build`.
Expected: clean; 200 passed; build succeeds. Run from `backend/`: `.venv/Scripts/python.exe -m pytest -q` — expected 333 passed (nothing changed, this confirms it).

- [ ] **Step 3: End-to-end check in the browser**

Start the backend (`flask run --port 5100` from `backend/` with the venv), hard-refresh `http://localhost:5100` (the SPA is served from `frontend/dist`, so a stale bundle looks exactly like a missing feature) and sign in as `admin@uniteduptime.com / ChangeMe123!`. Expected:
1. No strip on the dashboard (nothing open yet).
2. Open a request from My Requests → a filled tab appears with its number and description; open a second → two tabs, the second filled.
3. Click the first tab → lands on `/requests/:id` (view). Click Edit on a draft → the tab stays put and now remembers `edit`; go to step 3; click the other tab and back → step 3 is still selected.
4. Go to Messages → strip stays, no tab filled. Click a tab → back on that request.
5. Close the current tab → moves to its neighbour; close the last → `/requests`; strip disappears.
6. `+` → `/requests/new`; no tab until Save Draft, then the new request's tab appears on the step you were on.
7. Sign out, sign in as another user → no tabs (per-user key).

- [ ] **Step 4: Document in CLAUDE.md**

In the **Frontend layout** section: add `openRequests.ts` (the open-request tab store, per-user `localStorage`) to the list after `main.tsx`/`App.tsx`, and `RequestTabs.tsx` (the tab strip, mounted in `AppShell` between header and main) to the components list. Then add a new section directly after "## Pings (in-app messaging)":

```markdown
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
- Tests need `frontend/src/test-setup.ts` (vitest `setupFiles`): Node ≥ 22 ships an
  inert `globalThis.localStorage` that jsdom does not replace, so the shim installs
  an in-memory `Storage`. Any test touching the store clears it in `beforeEach`.
- No confirm on close (nothing is unsaved), no reorder/pin/close-all, no server-side
  persistence, no status badge on the tab, no nav change.
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md for open-request tabs"
```

---

## Self-Review

**Spec coverage.** §2 no backend change → every task is under `frontend/` + `CLAUDE.md`. §2 tab record, `localStorage`, label snapshot → Task 1. §2 strip in the shell, null when empty → Task 2 (component + `AppShell` mount). §2 active tab from URL → `activeRequestId`, tests "marks the request in the address bar…", "…not a request", "…new-request page". §2 insertion order / `seq` eviction / cap 8 → Task 1 tests "leaves a reopened request where it sits", "evicts the least recently opened". §2 per-user key + corrupt fallback → Task 1 tests. §2 close behaviour → Task 2 tests (neighbour, fallback, stays put). §2 one hook point → Tasks 3–4 touch effects; the sweep in Task 5 Step 1. §2 `+` → Task 2. §2 styling + `aria-current` + `aria-label="Close …"` → Task 2 verbatim classes. §2 404 branch → Tasks 3 and 4 with tests. §3.1 `mode`, `REQUEST_PATH`, `/requests/new` excluded → Tasks 1–2 (note: the regex as written in the spec does capture `new`; the strip treats that capture as no match, and a test pins it). §3.2 step on the tab, `location.state` fallback, mid-mount test that fails first → Task 3. **Beyond the spec (found while planning):** `WizardPage` also seeds its *form* once and never reseeds on an id change, so a tab switch between two drafts would show and save A's fields as B's — Task 3 reseeds on `routeId` change and the switch test pins it with `findByDisplayValue`. §3 no `replaceOpenRequest` → absent. §4 files → File Structure. §4 empty description → number alone → Task 2 test "shows the number alone…". §5 out of scope → nothing planned. §6 tests: 13 ported + 1 new store tests (14); 9 ported + 2 new strip tests + 1 for `/requests/new` (12); wizard mid-mount switch + 5 more; detail page 2. §7 `test-setup.ts` shim + `setupFiles` → Task 1 Step 1; no confirm on close → none.

**Placeholder scan.** No TBD/TODO; every code step has code; the sweep step names the expected destinations and what to do on a surprise.

**Type consistency.** `OpenRequest.mode: 'view' | 'edit'` in Task 1; `open(id, number, title, mode)` and `pathFor` in Task 2 use the same union; Tasks 3–4 pass `mode: 'edit'` / `mode: 'view'`. `touchOpenRequest(userId, { id, number, title, mode })` signature is identical at every call site. `readOpenRequests(userId)` is used by Task 3's touch effect and by both test files. The `X` icon comes from `lucide-react`, matching `AppShell`'s `LogOut` import style. `renderAt(path, extra?)` in Task 3 keeps the existing one-argument calls valid.
