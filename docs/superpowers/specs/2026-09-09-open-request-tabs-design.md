# Open-request tabs — design

**Date:** 2026-09-09. **Owner's ask:** *"adds tabs for each CAPEX request. This
should work similar to having multiple bids open at one time how the SCORE app
currently works. This should work same for CAPRI to have multiple items open in
different tabs."*

**Source to port from:** SCORE's bid tab strip, built 2026-08-14 and documented in
`bid_app/CLAUDE.md` §8 "The bid tab strip". The two files to read before writing a
line here are `bid_app/frontend/src/openBids.ts` (149 lines, the store) and
`bid_app/frontend/src/components/BidTabs.tsx` (102 lines, the strip), plus their
tests `openBids.test.ts` (16) and `components/BidTabs.test.tsx` (9). SCORE's
frontend is the same stack as CAPRI's (React 19, React Router 7, TanStack Query 5,
Tailwind v4, vitest), so the port is close to a copy with the names changed and
two CAPRI-specific differences handled (§3).

## 1. Problem

A requester or approver working several CAPEX requests at once leaves one, goes
through My Requests, finds the next, opens it, and later makes the same trip back.
Every trip is a list page and a search. SCORE had the identical complaint for bids
and answered it with a strip of tabs across the top of every page — one tab per
open bid — so switching is one click from anywhere, including Reports or Admin.

CAPRI has nothing like it. The nav's "New Request" highlights for the wizard, but
there is no memory of which requests the person has open.

## 2. What SCORE does, and why each part is the way it is

This is the design. CAPRI adopts all of it unless §3 says otherwise.

- **No backend change at all.** No route, no migration, no serializer. The wizard
  already persists every save server-side, so having several requests "open" was
  never a state problem — it is chrome over URLs that already exist. That is also
  why closing a tab needs no confirm dialog: nothing is lost.
- **A tab is a pointer plus a label snapshot**, stored in `localStorage`:
  `{ id, number, title, mode, step, seq }`. Ids alone would cost one request per
  tab on every page load, which an app-wide strip cannot afford. The page that
  loads a request refreshes its own tab's label, so a renamed request corrects
  itself on next open.
- **The strip lives in the app shell, not in the request pages**, and renders
  **nothing at all when no request is open** — not an empty bar. A first-time
  user sees the app unchanged.
- **The active tab is read from the URL**, never from stored state. The address
  bar is the one place that cannot drift from what is rendered.
- **On-screen order is insertion order and never changes.** Tabs that jump on
  click cannot be aimed at. `seq` is bookkeeping only: it stamps the last open so
  the cap evicts the least recently *seen*, not the leftmost.
- **Cap of 8.** Past it, the least recently opened tab is evicted silently.
- **Keyed by user**: `capri_open_requests:<userId>`. `localStorage` is per
  browser, not per account, and two people sharing a machine must not inherit
  each other's tabs. A corrupt or foreign stored value falls back to an empty
  set rather than throwing.
- **Closing the tab you are on** moves you to the tab to its right, else the one
  to its left, else to `/requests`. Closing any other tab leaves you where you
  are.
- **One hook point covers every entry path.** The request pages call the store's
  `touch` when their request loads. The list page, the dashboard, a deep link
  from an email, and the new-request redirect all arrive through those same
  routes, so nothing else needs wiring. SCORE verified this by sweeping every
  `navigate`/`Link` to a bid; do the same sweep here.
- **The strip's trailing `+` starts a new request** (`/requests/new`).
- **Styling**: outlined pills, the current one filled in the accent with bold
  text and `aria-current="page"` — weight and fill as well as colour, never
  colour alone. Each pill shows the number and a truncated title with the full
  pair in the hover title, and an `×` with `aria-label="Close CX000123"`.
- **A stored tab is exactly how a request that no longer exists gets opened.**
  The request pages must have an error branch: on a 404, close that tab and go
  to `/requests`, rather than sitting on "Loading…" forever. SCORE gained that
  branch the same day for exactly this reason.

## 3. What is different in CAPRI

Two things, both real, neither large.

**3.1 A request has two pages; a bid has one.** SCORE's tab always opens
`/bids/:id/edit`. CAPRI has `/requests/:id` (`RequestDetailPage`, the read view
approvers use) and `/requests/:id/edit` (`WizardPage`). A tab must remember
which one the person was on, or switching tabs throws an approver into edit mode.

So the tab record carries `mode: 'view' | 'edit'`. Both pages call `touch` with
their own mode when their request loads; clicking a tab navigates to
`mode === 'edit' ? /requests/:id/edit : /requests/:id`. The active-tab test
matches either path:

```ts
const REQUEST_PATH = /^\/requests\/([^/]+)(?:\/edit)?$/
```

`/requests/new` deliberately does not match — a request that has no id yet has no
tab. It gets one the moment the wizard's first save redirects to `/requests/:id/edit`
(`WizardPage.tsx:71` and `:95` already do that redirect), because that page then
loads it and calls `touch`.

**3.2 The wizard step must move out of `useState`.** `WizardPage` keeps `step` in
component state seeded from `location.state` (`WizardPage.tsx:41`). SCORE's
`BidWizard` did the same and it was already wrong before tabs: React Router keeps
the page mounted when only the `:id` param changes, so local step state carried
request A's step onto request B. With a strip it happens constantly. SCORE moved
the step into the tab record (`setOpenBidStep`) and read it back with a clamp
against the visible section count; there is a test that switches bids mid-mount
and was confirmed to fail against the local-state version.

Do the same here: `step` lives on the tab, `WizardPage` reads
`tabs.find(t => t.id === id)?.step ?? 0` (falling back to `location.state.step`
for the new-request redirect, which has no tab yet), and writes through
`setOpenRequestStep` on every step change. `RequestDetailPage` has no step and
leaves it alone.

**Not needed in CAPRI:** SCORE's `replaceOpenBid`. It exists because `revise()`
creates a *new* bids row and the old one is superseded, so the new revision swaps
into the same tab. A CAPEX request keeps one id for its life, so there is nothing
to swap. Do not port it.

## 4. Files

| File | Responsibility |
|---|---|
| Create `frontend/src/openRequests.ts` | the store: `readOpenRequests`, `useOpenRequests`, `touchOpenRequest`, `setOpenRequestStep`, `closeOpenRequest`, `MAX_OPEN_REQUESTS = 8`, `storageKey(userId)` |
| Create `frontend/src/components/RequestTabs.tsx` | the strip; reads the URL for the active tab; renders null when empty |
| Modify `frontend/src/components/AppShell.tsx` | mount `<RequestTabs userId={user.id} />` between the `<header>` and `<main>` (SCORE mounts it at `AppShell.tsx:126`, the same spot); render only when `user` is loaded |
| Modify `frontend/src/routes/RequestDetailPage.tsx` | `touch` on load with `mode: 'view'`; 404 branch closes the tab |
| Modify `frontend/src/routes/WizardPage.tsx` | `touch` on load with `mode: 'edit'`; step read from and written to the tab; 404 branch |
| `frontend/src/routes/RequestsListPage.tsx` | **untouched** — it has no delete action today (checked 2026-09-09), so there is nothing to close a tab from. If one is ever added, call `closeOpenRequest` on success, as SCORE does at `Bids.tsx:276` |
| Create `frontend/src/openRequests.test.ts`, `components/RequestTabs.test.tsx` | tests, §6 |

### The store

Port `openBids.ts` with these renames and the `mode` field added; nothing else
changes. Keep SCORE's comments — they say why.

```ts
export interface OpenRequest {
  id: string
  number: string        // "CX000123"
  title: string         // the request's description, truncated by CSS not here
  mode: 'view' | 'edit'
  step: number          // which wizard step it was left on; 0 for a view-only tab
  seq: number           // last-opened stamp; eviction only, never display order
}

export const MAX_OPEN_REQUESTS = 8
export const storageKey = (userId: string) => `capri_open_requests:${userId}`

export function readOpenRequests(userId: string): OpenRequest[]
export function useOpenRequests(userId: string): OpenRequest[]
export function touchOpenRequest(userId: string,
  req: Omit<OpenRequest, 'step' | 'seq'>): OpenRequest[]   // add, or refresh label + mode; keeps step
export function setOpenRequestStep(userId: string, id: string, step: number): OpenRequest[]
export function closeOpenRequest(userId: string, id: string): OpenRequest[]
```

`touch` on an existing tab spreads the stored tab first so its remembered `step`
survives, then overwrites `number`, `title`, `mode` and `seq`. The listener set and
`write()` (which also swallows a `localStorage` failure in private mode) come
across verbatim.

The label: `number` is `CapexRequestData.number`; `title` is
`CapexRequestData.description`. If `description` is empty, use the number alone
rather than inventing text.

### The strip

Port `BidTabs.tsx` with `REQUEST_PATH` from §3.1, tab click navigating by `mode`,
close falling back to `/requests`, and the `+` going to `/requests/new`. Keep the
class names — CAPRI's Tailwind tokens (`bg-accent`, `border-border`, `bg-surface`,
`bg-surface-2`, `text-muted`) already exist because SCORE's design system was
copied from CAPRI's (`BID-APP-STARTER-GUIDE.md` §4). Use CAPRI's own `X` icon from
`lucide-react` or `ActionIcons.tsx`, whichever the codebase uses for close
controls today.

### The two pages

```ts
// RequestDetailPage.tsx, after `req` loads
const { data: me } = useMe()
useEffect(() => {
  if (me && req) touchOpenRequest(me.id, { id: req.id, number: req.number,
                                           title: req.description, mode: 'view' })
}, [me?.id, req?.id, req?.number, req?.description])
```

The wizard does the same with `mode: 'edit'`, plus the step change from §3.2.
Both depend on primitive fields, not the object, so a refetch that returns an
equal request does not re-touch and bump `seq`.

## 5. Out of scope

- Drag-to-reorder, pinning, or a "close all" control — SCORE has none and nobody
  has asked.
- Persisting tabs server-side or across devices. `localStorage` is the whole
  store, by design.
- Showing status or an approval badge on the tab. The tab is a pointer; the page
  says the rest.
- Any change to the nav. The sidebar's "New Request" highlight for the wizard
  stays as it is.

## 6. Tests

Port the 25 SCORE tests one for one (names below are SCORE's; rename bid → request),
then add the three CAPRI-specific ones marked **new**.

`openRequests.test.ts`: is empty before anything is opened · remembers a request
that was opened · does not duplicate a request opened twice · refreshes a stale
label when reopened · leaves a reopened request where it sits in the strip ·
remembers which step each request was left on · keeps the remembered step when
reopened · ignores a step for a request that is not open · removes only the one
that was closed · evicts the least recently opened past the cap · keeps one
user's tabs out of another's · falls back to empty when the stored value is
corrupt · falls back to empty when it is not a list · **new:** reopening in the
other mode updates `mode` and keeps `step`.

(SCORE's three `replaceOpenBid` tests are dropped with the function.)

`RequestTabs.test.tsx`: renders nothing when no request is open · shows a tab for
each open request naming number and title · marks the request in the address bar
as current · marks no tab current when the page is not a request · switches to a
request when its tab is clicked · closes a tab without leaving the page you are
on · moves to a neighbour when the open one is closed · falls back to the list
when the last tab is closed · starts a new request from the trailing control ·
**new:** a `view` tab opens `/requests/:id` and an `edit` tab opens
`/requests/:id/edit` · **new:** `/requests/:id/edit` marks the same tab current
as `/requests/:id`.

`WizardPage.test.tsx`: add the mid-mount switch test — render at
`/requests/a/edit` on step 2, change the route to `/requests/b/edit`, assert step
is b's remembered step (or 0), not 2. Confirm it fails against the `useState`
version before fixing.

Gates, from `frontend/`: `node ./node_modules/vitest/vitest.mjs run`,
`node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` (CAPRI's
`tsconfig.json` is a real config with `"include": ["src", ...]`, so this
typechecks everything — unlike SCORE's references-only one), and
`node ./node_modules/vite/bin/vite.js build`. Then restart Flask and hard-refresh:
the SPA is served from `frontend/dist`, so a stale bundle looks exactly like a
missing feature.

## 7. Traps SCORE already paid for

- **The step in `useState` bug (§3.2)** — the one that bites constantly once a
  strip exists. Fix it as part of this, not after.
- **`localStorage` under vitest on Node ≥ 22.** Node ships an inert
  `globalThis.localStorage` that jsdom does not overwrite, so every storage test
  finds a dead stub. SCORE's `src/test-setup.ts` installs an in-memory `Storage`
  when the global is not usable. **CAPRI has no test setup file today** (checked
  2026-09-09), so expect this on the first run of the new store tests: copy
  SCORE's shim in as `frontend/src/test-setup.ts` and point vitest's
  `setupFiles` at it.
- **The per-user key is load-bearing**, not tidiness. Two people on one machine
  is the normal case for a shared workstation.
- **Do not add a confirm on close.** There is nothing unsaved to protect, and a
  dialog on every close is the fastest way to make the strip unused.
