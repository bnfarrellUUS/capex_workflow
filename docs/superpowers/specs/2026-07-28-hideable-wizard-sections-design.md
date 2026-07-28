# Hideable wizard sections — design

**Date:** 2026-07-28
**Status:** approved, ready for implementation plan

## Problem

The New Request wizard has seven fixed steps. Not every organization needs all
of them — the Economic step in particular asks for IRR, EBIT, NPV and payback
figures that many requestors cannot supply. Today an admin has no way to remove
a step, and the wizard's step numbers are hardcoded positions, so removing one
would leave a gap in the numbering.

An ADMIN needs to choose which wizard sections requestors see, and the visible
steps must renumber consecutively.

## Scope

Five sections are hideable:

| key | wizard step |
| --- | --- |
| `description` | Description |
| `effect_on_ops` | Effect on Ops |
| `asset_details` | Asset Details |
| `economic` | Economic |
| `attachments` | Attachments |

**Basic Info and Review are always visible.** Basic Info holds the Division,
which drives Level-1 approver routing (a request without a division cannot
route), plus the request date and asset description shown throughout the app.
Review is where Submit lives. Neither is offered as a toggle, and the API
rejects them as hideable keys.

Reordering sections is **out of scope**.

## Storage

One row in the existing `AppSetting` key/value table:

- key `wizard_hidden_sections`
- value: a JSON array of hidden section keys, e.g. `["economic"]`
- absent row (the default) means nothing is hidden

Chosen over a dedicated `RequestSection` table because this is five booleans of
configuration. It reuses the `settings_service` / `AppSetting` pattern already
carrying the email delivery mode, and needs **no Alembic migration**. A table
would only pay off for reordering or per-division variation, neither of which
is in scope.

`settings_service` gains, alongside the email helpers and sharing its `_get` /
`_set` primitives:

- `get_hidden_sections() -> list[str]` — parses the JSON value; returns `[]`
  when unset, and tolerates a malformed value by returning `[]` rather than
  raising
- `set_hidden_sections(keys) -> list[str]` — writes and commits, returns the
  stored list

## API

New blueprint `backend/app/blueprints/request_sections.py`, mounted at
`/api/request-sections`:

- `GET` → `{"hidden": ["economic"]}` — **any authenticated user.** The wizard
  needs this config, so it is not ADMIN-gated like `/api/email-templates/settings`.
- `PUT` `{"hidden": [...]}` → same shape — `@require_roles("ADMIN")`.

Input is validated by `backend/app/schemas/request_sections.py`
(`HiddenSectionsIn`): the list must contain only the five keys above.
Unknown keys, `basic_info` and `review` are rejected with 400. Duplicates are
collapsed.

Register the blueprint in the app factory next to the other blueprints.

### Not a security boundary

This is display configuration. `RequestDraft` / the PATCH route continue to
accept the fields of a hidden section. That is deliberate:

- existing request data is never deleted or made unsaveable by a config change
  (see "Existing data" below)
- it avoids a second source of truth about which fields are writable

## Wizard refactor

`frontend/src/routes/WizardPage.tsx` currently declares

```ts
const STEPS = ['Basic Info', 'Description', …, 'Review']
```

and renders each step by its position (`{step === 4 && <Economic … />}`). That
positional coupling is exactly what makes numbering fragile, so it is replaced
by a keyed registry — one entry per section with its key, label, an `always`
flag for Basic Info and Review, and its rendered body:

```ts
SECTIONS = [
  { key: 'basic_info',   label: 'Basic Info',    always: true },
  { key: 'description',  label: 'Description' },
  { key: 'effect_on_ops',label: 'Effect on Ops' },
  { key: 'asset_details',label: 'Asset Details' },
  { key: 'economic',     label: 'Economic' },
  { key: 'attachments',  label: 'Attachments' },
  { key: 'review',       label: 'Review',        always: true },
]
```

The visible list is derived once per render:

```ts
visible = SECTIONS.filter((s) => s.always || !hidden.includes(s.key))
```

The stepper maps over `visible` and renders `i + 1`, so hiding Economic makes
Attachments **5** and Review **6** with no further arithmetic. `step` remains
an index into `visible`; `Next` / `Back` / `goToStep` and the
`STEPS.length - 1` last-step check all read from `visible`.

The hidden-sections config is fetched with TanStack Query (`['request-sections']`).
The wizard already returns `Loading…` until `form` is seeded — it now also waits
for the config, so the stepper never renders with the wrong numbering and then
reflows.

**Clamp:** if the config changes while a requestor sits on a step (or a stale
`location.state.step` arrives from a Save Draft navigation), `step` is clamped
to `visible.length - 1` so it can never point past the end.

### Review step summary

The Review step's summary lines follow the same visibility rules: no "Asset
line items" / "Total cost" lines when Asset Details is hidden, and no
"Attachments" count when Attachments is hidden.

## Admin page

`frontend/src/routes/admin/RequestSectionsPage.tsx` at
`/admin/request-sections`, ADMIN-only, added to the sidebar under
Administration between Approval Thresholds and Email Templates. It uses one
`BrandCard` with `mark="newRequest"` — it configures that page — and lists all
seven sections in wizard order:

```
┌─ Request Sections ─────────────────┐
│ Choose which steps requestors see.  │
│                                     │
│  1  Basic Info        (always)      │
│  2  Description       [● shown ]    │
│  3  Effect on Ops     [● shown ]    │
│  4  Asset Details     [● shown ]    │
│  —  Economic          [  hidden ○]  │
│  5  Attachments       [● shown ]    │
│  6  Review            (always)      │
│                            [Save]   │
└─────────────────────────────────────┘
```

Each row shows the step number it will carry once saved, or `—` when hidden, so
the admin sees the resulting numbering live while toggling. Basic Info and
Review render as `(always)` with no control. Save `PUT`s the hidden list and
invalidates the `['request-sections']` query.

The Asset Details row carries a warning line: hiding it means requests have no
equipment line items, so `total_cost` is `0` — and since `required_levels`
derives from `total_cost` against the `ApprovalThreshold` caps, every request
would route at Level 1 only. This is a documented consequence of the toggle,
not a defect to work around.

The sidebar entry reuses the existing `NewRequestIcon` from `NavIcons` — no new
icon is drawn.

## Request detail page

Hidden sections also drop out of the request view, so approvers and finance
don't read rows of `—`:

- `description` → the `FullDetails` "Justification" block
- `effect_on_ops` → the `FullDetails` "Effect on operations" block
- `economic` → the `FullDetails` "Economic analysis" block
- `asset_details` → the equipment-items table on the main detail page

**Exception — Attachments stays visible.** The detail page's Attachments
section is not a mirror of the wizard step; it is the live tool FINANCE uses to
attach files once a request is APPROVED. Hiding the wizard step must not remove
that capability, so that section ignores the config.

`RequestDetailPage` fetches the same `['request-sections']` query.

## Existing data

Hiding a section **never deletes data**. Values already stored in a hidden
section stay in the database; they are only omitted from the wizard and the
detail view. Re-showing the section brings them back unchanged. There is no
migration, no backfill, and no destructive path.

## Testing

Backend (`cd backend && pytest -q`):

- `GET /api/request-sections` with no row set → `{"hidden": []}`
- `PUT` as ADMIN persists, and a following `GET` returns the saved list
- `PUT` as a non-ADMIN user → 403
- `GET` as a plain REQUESTOR → 200 (config is readable by everyone)
- `PUT` with an unknown key → 400
- `PUT` with `basic_info` or `review` → 400
- hiding a section does not reject a PATCH that still sends its fields

Frontend (`npm test`):

- the visible-sections helper renumbers correctly with Economic hidden
  (Attachments 5, Review 6) and with several sections hidden
- the wizard skips a hidden step when advancing with Next
- `step` is clamped when it exceeds the visible count
- the admin page renders the toggles, shows live numbers, and saves

Then the full gate: `pytest -q`, `node ./node_modules/typescript/bin/tsc
--noEmit -p tsconfig.json`, `node ./node_modules/vite/bin/vite.js build`.

Existing `RequestDetailPage` tests build full request mocks — they need the new
query mocked so the detail page keeps rendering.

## Docs

`CLAUDE.md` gains: the new blueprint in the backend list, the
`settings_service` hidden-sections helpers, the new admin route and sidebar
entry, and a note in Conventions that wizard steps are a keyed registry — new
steps are added there, not by positional index.
