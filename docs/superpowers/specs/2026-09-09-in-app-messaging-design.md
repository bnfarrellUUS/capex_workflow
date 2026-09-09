# In-App Messaging ("Pings") — Design

**Date:** 2026-09-09
**Status:** agreed with the owner in-session (2026-09-09)
**Ported from:** SCORE's `bid_template/bid_app/docs/superpowers/specs/2026-09-01-in-app-messaging-design.md`
(itself a port of ARIA's `ar_dashboard/docs/superpowers/specs/2026-08-21-in-app-messaging-design.md`),
re-cut for CAPRI's domain. SCORE's implementation is **complete and shipped**
(`ping_service.py`, `pings.py`, `test_pings.py`, `PingBell`/`PingPanel`/`PingModal`/
`PingDetail`/`PingCard`/`Pings.tsx`), and CAPRI runs the same stack, so this is a
file-by-file port with the context kinds swapped — not a rewrite from a document.

## 0. Purpose

Let CAPRI users route work to each other without leaving the app: an approver
pings Finance about a GL account before signing, a requestor pings their
division's L1 approver to say a quote was updated, Finance pings a requestor for
an asset number. The recipient gets an in-app item, works it, replies if needed,
and ticks it done.

This is a **work-routing inbox with a conversation attached** — not a chat
client, and not a second approval mechanism. A ping never moves a request's
status, level or assignee.

## 1. Naming

Two words, deliberately split, matching ARIA:

- **Sidebar and full page say "Messages"** (owner, 2026-09-09): nav label
  `Messages`, route `/messages`, page title "Messages".
- **Everything else says "Ping"**: the header bell's items, every button
  ("Ping", "New Ping"), the modal, and all code — tables `pings` /
  `ping_recipients`, service `ping_service.py`, blueprint `pings.py`, schema
  `schemas/pings.py`, routes `/api/pings`, components `PingBell` / `PingPanel` /
  `PingModal` / `PingDetail` / `PingCard`, page component `MessagesPage.tsx`,
  API client `api/pings.ts`.

Never `message` in code, never `handoff` anywhere.

## 2. Data model

Two new tables. Ids are **`String(36)` UUIDs via the existing `_id` default**
in `models/__init__.py`, like every CAPRI model — **not** SCORE's `String(32)`
PK mixin, which is the single most likely thing to be copied across by mistake.
Timestamps are plain `DateTime` defaulting to `_utcnow`, as on `RequestComment`
and `ApprovalAction`; a ping is immutable once sent, so there is no
`updated_at`.

### 2.1 `pings`

| column | type | notes |
|---|---|---|
| `id` | `String(36)` PK | `_id` default |
| `parent_id` | `String(36)` FK → `pings.id`, null | null = conversation root; set = a reply |
| `sender_id` | `String(36)` FK → `users.id` (`ondelete="NO ACTION"`), not null | |
| `note` | `Text` not null | free text, non-blank |
| `request_id` | `String(36)` FK → `capex_requests.id` (`ondelete="NO ACTION"`), null | optional context, §4 |
| `created_at` | `DateTime` not null | `_utcnow` |

**A reply is a child row, not a separate table.** `parent_id` points at the
conversation root — never at another reply — so a thread is exactly two levels
deep and one conversation is one root row. The list query groups by root, so a
twelve-reply exchange is one line in the inbox.

**`request_id` is `NO ACTION`, not cascade.** Owners can delete their own drafts
(`DELETE /api/requests/<id>`). A draft with pings attached is refused rather
than silently orphaning the conversation: `request_service.delete_draft` counts
`pings` rows for the request **before** deleting and raises
`ServiceError("This draft has messages attached and cannot be deleted.", 409)`.
The check is explicit because CAPRI does not turn on SQLite's
`PRAGMA foreign_keys`, so the FK alone would not fire in dev or tests; on SQL
Server the `NO ACTION` FK is a second line of defence. Pings about a draft are
rare, and a refused delete is a clearer outcome than a ping whose subject has
vanished.

### 2.2 `ping_recipients`

| column | type | notes |
|---|---|---|
| `id` | `String(36)` PK | |
| `ping_id` | `String(36)` FK → `pings.id`, not null | |
| `user_id` | `String(36)` FK → `users.id`, not null | |
| `read_at` | `DateTime` null | stamped on that person's first open |
| `completed_at` | `DateTime` null | stamped when that person ticks done |

Unique on `(ping_id, user_id)`. Who a ping is addressed to lives here, never on
the `pings` row.

Cap: **25 recipients per ping**, enforced in the service.

### 2.3 No `ping_lines`

SCORE pinpoints bid lines; CAPRI's equivalent (equipment items) was considered
and dropped (owner, 2026-09-09, option 1 of three). A ping is about a request,
or about nothing.

### 2.4 Migration

One Alembic revision, `<rev>_pings.py`, creating both tables. Purely additive:
no existing table is altered, nothing is backfilled, `seed.py` needs no new
rows. Down-revision is the current head — check `flask db heads` at
implementation time, don't assume.

## 3. Status, and the two rules that are not obvious

Status is **derived, never stored**:

- **unread** — this viewer's `ping_recipients.read_at` is null
- **read** — stamped, not yet closed
- **done** — closed (see below)

### 3.1 Read is personal

`read_at` is per recipient. A group ping read by two of five people is unread
for the other three; each person's badge reflects only their own row.

### 3.2 Done is shared

**A group ping is one job, not one job each.** Whoever ticks first closes it for
the whole roster, and the UI names them ("Done by Dana Ruiz"). Earliest tick
wins, so a second person ticking through a stale page cannot rewrite who
finished it — their tick is still recorded on their own row, which the roster
in the detail view shows.

Derived at read time from the recipient rows (SCORE's `apply_shared_done`,
ported verbatim), not stored.

### 3.3 An answered ping is in both boxes

A conversation the sender **started** returns to their inbox once someone
replies: the reply is addressed to them. `Sent` stays "exchanges I opened". An
answered ping therefore appears in both, which is what surfaces the answer.

### 3.4 Ordering

Conversations sort by newest activity — the latest reply, falling back to the
root — ordered by `(last_activity_at DESC, last_activity_id DESC)`. Ids in
both SCORE and CAPRI are random `uuid4().hex`, **not** monotonic, so the id is
only a deterministic tiebreaker for rows stamped in the same instant, never a
recency key by itself. (SCORE's design doc says "by row id"; its shipped
`_summarize` already does created_at-then-id, and that is what is ported.) The
same-second test pins the tiebreak.

## 4. Context: the request

One attachment kind, optional. A ping with no context is legal — a note to a
colleague.

### 4.1 Live summary

The detail view renders the request live, never a snapshot: `number`, `status`
(via the existing `StatusBadge`), `division_name`, `requestor_name`,
`total_cost` — the same five fields `request_service.request_out` already
emits for list rows, produced by a `_request_summary(viewer, request_id)`
helper in `ping_service` that also returns `visible` (§5).

### 4.2 A ping is context, never a nudge

It does not route, does not appear in `eligible_actors`, does not satisfy or
block a level, and does not send the approval emails. CAPRI already notifies
approvers through `notify` on each transition; a ping that also emailed them
would be a second notification system firing on the same event.

## 5. Scope: pings are deliberately unscoped

**Anyone signed in can ping anyone else signed in.** The directory is every
active user, unfiltered by role, division or `_can_view`. Carried over from
SCORE (owner, 2026-09-01: "can ping anyone in app, it can also help if need
quicker") and reaffirmed for CAPRI (2026-09-09).

The consequence, stated so it is a decision rather than a bug report later:
**a ping can reference a request the recipient cannot open.** The detail view
always renders the request summary so the conversation makes sense, and the
deep link to `/requests/<id>` is rendered **only when
`request_service.can_view(req, viewer)` is true** — a link that 403s reads as
broken software. Nothing about this widens request visibility itself; every
other route stays scoped exactly as today.

## 6. Pings versus the comment thread

Both stay, and they are different things:

| | Comment thread (`RequestComment`) | Ping |
|---|---|---|
| Addressed to | the request — everyone who can view it | named people |
| Visibility | anyone who can view the request | sender + roster only |
| State | none (immutable log) | per-person read, shared done |
| Record PDF | printed under Approval history | never |
| Email | yes (`COMMENT` template, other side) | no (§9) |
| Can reference | its own request only | any request, or nothing |

The comment thread is the request's own record; a ping is a task for a person.
Pings never appear in the PDF and are never part of the audit copy. Don't merge
them, and don't make pings print.

## 7. Backend

Conventions as elsewhere in CAPRI: thin blueprint, fat service,
`ServiceError(message, status)` mapped to JSON by `create_app`, Pydantic v2
input with **type constraints rather than raising validators** (a
`field_validator` that raises puts an unserializable object under
`errors()['ctx']` and the 400 becomes a 500 — the same trap `CommentIn`
avoids with `StringConstraints`).

### 7.1 `app/services/ping_service.py`

Ported from SCORE with the bid/customer/approval-rule/line code removed:

- `create_ping(sender, *, recipient_ids, note, request_id=None, parent_id=None) -> Ping`
- `list_pings(viewer, box)` — `inbox` or `sent`; roots only, newest activity
  first (§3.4), capped at 200, each carrying roster, reply count, unread-reply
  count for this viewer, the shared-done overlay, and the request summary
- `get_ping(viewer, ping_id)` — root + replies + live request summary; 403
  unless sender or on the roster; stamps `read_at` when a recipient fetches
- `unread_count(viewer)`
- `complete_ping(viewer, ping_id)` / `reopen_ping(viewer, ping_id)` — roster only
- `reply(viewer, ping_id, note)` — sender or roster; child row addressed to
  everyone else in the conversation
- `directory()` — active users as `{id, name, email, roles, division_name}`, by name
- `suggested_recipients(viewer, request_id)` — the people most likely to
  answer, ranked first in the picker: the **requestor**; while the request is
  `PENDING_L*`, the **eligible approver pool at `current_level`** via
  `workflow_service.eligible_actors(level, division, thresholds,
  exclude_id=requestor_id)` — the requestor exclusion is threaded through like
  everywhere else; once `APPROVED`, every active **FINANCE** user. The viewer
  is removed from their own suggestions. Matching is on user id from the
  request's own fields, never on name text.

Dropped from SCORE: `pings_for_bid` and the `/bids/<id>/pings` route. Nothing
in v1 lists a request's pings on the request page.

Services stay email-free: nothing here calls `notify`.

### 7.2 `app/blueprints/pings.py`

All `@login_required`. No `require_roles` — every role pings (§5). Registered
in `create_app` beside the others.

| route | behaviour |
|---|---|
| `GET /api/pings/unread_count` | `{ok, count}` for the current user |
| `GET /api/pings?box=inbox\|sent` | conversation list |
| `GET /api/pings/directory` | active users for the picker |
| `GET /api/pings/suggestions?request_id=` | suggested recipients (§7.1) |
| `GET /api/pings/<id>` | root + replies + summary; 403 unless sender or recipient; stamps read |
| `POST /api/pings` | create; body `PingCreateIn` |
| `POST /api/pings/<id>/reply` | add a reply |
| `POST /api/pings/<id>/done` | tick done (shared, §3.2) |
| `POST /api/pings/<id>/reopen` | untick |

Route order matters: `directory`, `suggestions` and `unread_count` are declared
before `/<ping_id>` so they are not captured as ids.

### 7.3 `app/schemas/pings.py`

`PingCreateIn` (`recipient_ids: list[str]` min 1, `note: str`,
`request_id: str | None`) and `PingReplyIn` (`note: str`), both
`extra="forbid"`. Blank-note, cap and existence checks live in the service and
raise `ServiceError`.

## 8. Frontend

React 19 + TanStack Query 5 + Tailwind v4. **There is no live dev server** —
rebuild with `node ./node_modules/vite/bin/vite.js build` to see a change.

### 8.1 Files

- `src/api/pings.ts` — typed client (port; drop bid/customer/line types)
- `src/routes/MessagesPage.tsx` — the full page at `/messages` (§8.3)
- `src/components/PingBell.tsx`, `PingPanel.tsx`, `PingCard.tsx`,
  `PingDetail.tsx`, `PingModal.tsx`
- `src/components/NavIcons.tsx` — new `MessagesIcon` in the same 24px
  `currentColor` line style as the other nav icons
- `src/components/AppShell.tsx` — one nav entry, `{ to: '/messages', label:
  'Messages', icon: MessagesIcon, roles: [] }`, in the top group after My
  Requests; the bell in the header
- `src/components/ui/Button.tsx` — a `size` prop (§8.6)
- `src/App.tsx` — `<Route path="/messages" element={<MessagesPage />} />`
  inside `ProtectedLayout`

### 8.2 The bell

🔔 in the existing header (`border-b border-border bg-surface px-6 py-3`),
between the user's name and the theme toggle. Unread badge is **solid
`#ef4444`**, 16px, radius 9, offset −7/−7, capped at "99+", and absent at zero.

**The emoji is kept deliberately.** CAPRI's convention is custom icons on a
24px grid and this is an explicit exception, inherited from SCORE at the
owner's request: the yellow bell is the recognisable affordance across ARIA,
SCORE and CAPRI, and users move between the apps.

Unread count polls every 30s via TanStack Query `refetchInterval: 30_000`.
Invalidate the `['pings']` keys after every ping action so the badge and lists
update at once.

### 8.3 The Messages page is a table

`/messages` renders a table in **CAPRI's own table idiom** — the one
`RequestsTable` uses: `w-full border-collapse text-sm`, header row
`border-b border-border bg-brand-sky/25 text-left text-xs uppercase
tracking-wide text-brand-navy dark:bg-brand-sky/10 dark:text-brand-sky`, body
rows `border-b border-border last:border-0 hover:bg-surface-2`. **Not** SCORE's
navy DataGrid header: that is SCORE's idiom, and CAPRI's tables are sky-tinted.

Layout follows what the owner settled on for SCORE (2026-09-01) after using
it: title and **New Ping** on one line, then full-width **Inbox / Sent**
underline tabs, a search box, and the status filter chips (Open / Unread /
Read / Done, each with a count; default Open so done work leaves the working
list).

Columns: **From / To** · **Ping** (note preview) · **Request** (number chip)
· **Replies** · **Status** · **Last activity**. Unread rows carry an accent dot
and semibold sender. **Clicking a row expands the detail inline** — a
full-width row directly beneath it hosting `PingDetail`; clicking again
collapses it. Not a side panel: the owner's SCORE feedback was "instead of it
expanding on the screen to right it would probably be better just expand down
in same panel", and a request link inside the expanded row then navigates with
nothing to dismiss first.

The page header uses `BrandCard` with a new `messages` mark key mapped to
`MessagesIcon`, like every other page.

### 8.4 The slide-over panel

The bell's quick view: 440px, right-anchored, light `--color-surface` with a
`--color-border` edge (not ARIA's dark navy slab), Inbox / Sent tabs, search,
the same filter chips, `PingCard` list. Search matches sender, recipients,
request number, the note and **every reply in the conversation**.

### 8.5 The New Ping modal

One shared `PingModal` behind every entry point; an entry point differs only in
the `{recipients?, request?}` it passes.

- **To:** multi-select from the directory. **Suggested** first (§7.1), then all
  users grouped by role.
- **Request:** read-only summary chip with a ✕ to clear it.
- **Note:** required.

### 8.6 Buttons: coloured, and not too large

Owner, 2026-09-09: "the buttons should have color and size not too large."

- `Button` gains `size?: 'md' | 'sm'`. `md` is today's `px-4 py-2 text-sm`
  (default, nothing else changes); `sm` is `px-3 py-1.5 text-xs`. A prop, not
  a className override — two competing padding utilities resolve by stylesheet
  order, not class order, so overriding is unreliable in Tailwind.
- **Every Ping button is `variant="primary" size="sm"`** (filled
  `--color-accent`, white text) with a 14px paper-plane glyph: the request
  detail header "Ping", and "New Ping" on the panel and the Messages page. It
  reads as an action, sits visibly smaller than Download PDF / Approve, and is
  never a grey secondary.
- On **table rows**, where actions are icon-only (`ViewIcon` at 18px), the
  Ping control is a paper-plane icon button of the same footprint coloured
  `text-accent`, beside View — so it stands out from the grey row icons without
  adding a text button to a dense row.

### 8.7 Entry points (v1)

1. **Request detail** — "Ping" beside Download PDF in the header; attaches the
   request and pre-fills suggestions.
2. **Requests list and Dashboard approvals table** — the row paper-plane
   (§8.6) on the shared `RequestsTable`; attaches that request.
3. **Messages page and panel** — "New Ping" with no context.

### 8.8 Token map

| role | SCORE | CAPRI |
|---|---|---|
| Unread badge | `#ef4444` | `#ef4444` — kept |
| Action / unread | `--color-accent` `#2563EB` | `--color-accent` `#2563EB` — same value |
| Done | `green-700` | `green-700` (`#15803d`) |
| Read / muted | `--color-muted` | `--color-muted` |
| Panel surface / border | `--color-surface` / `--color-border` | same tokens |
| Table header | `--color-brand-navy` (DataGrid) | `bg-brand-sky/25 text-brand-navy` (RequestsTable) |
| Bell glyph | 🔔 emoji | 🔔 emoji — kept |

Status pills stay **outlined, never filled**.

## 9. Out of scope for v1

**Email notification.** CAPRI has the whole rail — `NotificationLog`, editable
templates, Test/Live delivery — so a `PING_RECEIVED` type would be cheap. It is
deferred anyway, as in SCORE: in-app delivery with a 30-second badge is the
point, and a system where every ping also generates mail is one where people
learn to ignore both. Revisit if pings go unread in practice; the measurement is
`read_at` staying null.

Also out: editing or deleting a sent ping; file attachments (files belong on the
request via `Attachment`); listing a request's pings on its detail page; an
admin oversight view; pinging people without a CAPRI account; reporting.

## 10. Error handling

- Blank note, unknown or inactive recipient, >25 recipients, unknown
  `request_id`, `parent_id` that is not a root → **400**, rendered in the modal.
- Detail fetch by someone neither sender nor recipient → **403**.
- `done` / `reopen` / `reply` by a non-participant → **403**.
- A referenced request the viewer cannot open → summary renders, deep link
  suppressed (§5).
- Deleting a draft that has pings → **409** (§2.1).

## 11. Testing

`backend/tests/test_pings.py`, pytest against the `create_all()` fixture and
`tests/factories.py` (`make_user`, `make_division`, `make_draft`,
`set_thresholds`):

- table creation; send → appears in the recipient's inbox and the sender's
  sent box
- unread count; detail fetch by a recipient stamps `read_at` and the count drops
- **read is personal**: two recipients, one opens, the other still unread
- **done is shared**: one ticks, all see done, `done_by` names the first
  ticker; a later tick does not rewrite it but is recorded on that person's row
- reply round-trip; an answered ping appears in the sender's inbox (§3.3)
- ordering: two rows created in the same second come out deterministically (§3.4)
- 403s: third-party detail fetch, non-participant done/reopen/reply
- 400s: blank note, inactive recipient, oversized roster, unknown request,
  reply to a reply
- request summary renders for a viewer outside `can_view` with the deep link
  suppressed, and with it present for the requestor
- suggested recipients: requestor + L1 pool while `PENDING_L1`; requestor
  never suggested as an approver of their own request; FINANCE once `APPROVED`
- unscoped directory returns users across divisions and roles (§5)
- deleting a draft with a ping attached returns 409

Frontend: vitest for `MessagesPage` (table renders, filter chips count, unread
styling), `PingBell` (badge states, 99+ cap, hidden at zero), `PingPanel`,
`PingModal` (suggested-first, request chip clear, submit disabled on blank
note) and `PingDetail`, ported from SCORE's tests and following
`CommentThread.test.tsx`. Then the gates from CLAUDE.md: `pytest -q`,
`node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`,
`node ./node_modules/vitest/vitest.mjs run`,
`node ./node_modules/vite/bin/vite.js build`.

## 12. Open question

**Should an open ping show on the request?** An approver with a question can
now ask without rejecting, but the request page says nothing about a pending
answer. An open-ping count on the detail page (what SCORE's `pings_for_bid`
was for) would fix that without giving pings any authority over state.
Deferred until the feature has been used; noted so the next session does not
treat the missing endpoint as an oversight.

**Should the sender be able to close a conversation they started?** §7.1 makes
done/reopen roster-only and §3.3 returns an answered conversation to the
sender's inbox, so today the sender sees it under Open until a recipient ticks
it. Flagged by the 2026-09-09 final review; deferred to the owner.
