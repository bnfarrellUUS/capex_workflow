# Regions, region-VP L2 routing, and no self-approval — design

**Date:** 2026-08-31
**Status:** Approved by Bryan (in-chat design review)

## Problem

1. The company is organized as ~5 **regions**, each containing several of the
   25–30 **divisions**. The app has divisions only, with no grouping above
   them.
2. Level-2 approval should be performed by the **VP of the request's region**,
   not by the current single global L2 pool on the `ApprovalThreshold` row.
3. Nothing stops a user from **approving their own request** when they happen
   to sit in an approver pool (or act as someone's delegate).

## Decisions (confirmed with Bryan)

- L1 unchanged (division pool). **L2 comes from the region's VP pool.** L3
  unchanged (global threshold pool). Dollar caps (`max_amount`) still decide
  `required_levels`.
- The region VP is a **pool** (any one may act), supporting backups — same
  semantics as every other level.
- **Region is required** on a division. No fallback to the old global L2 pool.
- Self-approval: the requestor is **excluded from every pool**, and if that
  (or a genuinely unconfigured pool) leaves a level empty, the request
  **skips to the next level up** (option B). Example confirmed: a request
  needing only L1 whose requestor is the sole L1 approver escalates to the
  region VP at L2.
- Every request must receive **at least one approval from someone other than
  the requestor**. If no level 1–3 has an eligible actor, submit fails with a
  clear error.
- The requestor is also blocked from acting **as someone's delegate** on their
  own request.

## Approach considered and rejected

Keep the global L2 threshold pool and add a per-region override. Rejected:
region is required, so the fallback would be dead config that confuses admins.
L2 approvers live on the Region, period.

## Data model

- **New `Region` model** (`regions` table): `id` (uuid string, as elsewhere),
  `name` (String(150)), `active` (Boolean, default True), and
  `vp_approvers: Mapped[list[User]]` via a new `region_vp_approvers`
  association table — an exact mirror of `Division.l1_approvers` /
  `division_l1_approvers`.
- **`Division.region_id`**: nullable FK to `regions.id` (`ondelete="NO
  ACTION"`, matching existing FKs) + `region` relationship. Nullable at the
  schema level because existing rows predate regions; the *form* requires it,
  and routing errors clearly when it is missing (see Routing).
- One Alembic migration adds `regions`, `region_vp_approvers`, and
  `divisions.region_id`. Existing divisions are left with `region_id` null;
  admins assign regions through the Division form (which now requires one to
  save).
- `ApprovalThreshold` table unchanged. The level-2 row's `approvers`
  many-to-many stops being consulted and its admin UI is removed; rows/data
  are left in place (harmless, avoids a destructive migration).

## Routing changes (`backend/app/services/workflow_service.py`)

- `intended_approvers(level, division, thresholds)`: level 2 returns
  `division.region.vp_approvers` when the division has a region, else `[]`.
  Levels 1 and 3 unchanged.
- `eligible_actors(...)` gains the requestor exclusion: after mapping each
  intended approver through their delegate, drop any actor whose id is the
  requestor's. This kills both cases at once — the requestor sitting directly
  in a pool, and the requestor being the *effective* actor because they are
  an approver's delegate. Signature grows a `requestor_id` argument (callers:
  `first_assignee`, `_require_current_approver`, and `request_service`'s
  worklist/visibility logic — see below).
- **Skip-empty-levels scan.** New helper (e.g. `_next_level(req, after,
  thresholds)`): the lowest level in `(after, 3]` whose eligible pool is
  non-empty. Used in two places:
  - `_open_workflow`: the first pending level is `_next_level(req, 0, ...)`
    rather than hard-coded 1. If none exists → `ServiceError` ("No one is
    able to approve this request. …"). The message names the actual gap when
    identifiable (division has no L1 approver besides you / division has no
    region / region has no VP).
  - `approve()`: a request is **APPROVED** when the acting level is
    `>= required_levels`; otherwise the next level is `_next_level(req,
    level, ...)`. If required levels remain but no higher level has an
    eligible actor → `ServiceError` at approve time (same behavior class as
    today's "No approver configured for level N").
  - Note the escalation property falls out naturally: when levels ≤
    `required_levels` are all empty, `_next_level` lands above
    `required_levels`, and that single approval finishes the request.
- The empty-pool skip applies uniformly — a level emptied by the requestor
  exclusion and a level with no approvers configured at all behave the same.
- `_acted_for` picks up the same requestor exclusion implicitly (it compares
  against eligible actors' logic; keep it consistent).
- `request_service._can_view` and the "assigned to me" worklist already
  resolve eligible actors per level; they must pass the request's
  `requestor_id` through so an excluded requestor doesn't see their own
  request on their approvals worklist (they still see it as its owner).

## API

- New `regions` blueprint at `/api/regions`, a straight copy of the
  `divisions` blueprint's shape: list (any signed-in user — the Division form
  needs it; matches how divisions/users lookups work), create/update
  ADMIN-only. Payload: `name`, `active`, `vp_approver_ids: list[str]`.
- `divisions` blueprint: `region_id` accepted on create/update (Pydantic
  schema field), echoed in `division_out` along with `region_name` for list
  display.
- Threshold PUT keeps accepting `approver_ids` for L3 (and technically L2 —
  it just has no effect and no UI); simplest is to leave the schema alone.

## Frontend

- **Admin → Regions**: `RegionsPage` (list: name, VP count, active) +
  `RegionNewPage`/`RegionEditPage`/`RegionForm` (name, active checkbox, VP
  pool via `TransferList`), cloned from the Division pages. Sidebar entry in
  the admin group with a new `regions` key in `NavIcons` and `BrandCard`'s
  mark map (icon style: 24px grid, rounded joins, `currentColor` — e.g. a
  map-pin/globe motif consistent with the set).
- **`DivisionForm`**: required Region `Select` fed by the regions list query;
  client-side "Region is required" validation on save.
- **`ThresholdsPage`**: the L2 card keeps its `max_amount` input; its
  TransferList is replaced with a short note: "Level 2 approvers come from
  each region's VP list (Admin → Regions)."
- `api/regions.ts` client module mirroring `divisions.ts`.

## Deliberately unchanged

- Requests keep storing `division_id` only; region resolves through the
  division at action time, so moving a division to a new region redirects
  future L2 approvals with no data migration. In-flight requests re-resolve
  pools on every action (already true today).
- No region column on the requests list, detail page, record PDF, or xlsx
  export for now.
- L3 remains the global threshold pool. `DEFAULT_PASSWORD`, emails, comments,
  finance flow: untouched.

## Testing

- Backend (pytest): region CRUD + authz; L2 routes to the region VP pool;
  missing region / empty VP pool errors at the right moment with the right
  message; self-approval exclusion — requestor in L1 pool (others still act),
  requestor as an approver's delegate (blocked), sole-approver escalation
  (L1-only request lands at L2), nobody-anywhere submit failure; skip-level
  approval sequences (L2 empty → L1 then L3); excluded requestor absent from
  the approvals worklist; existing suite stays green (threshold L2 pool tests
  updated to the new source of truth).
- Frontend: vitest for `RegionForm`/`DivisionForm` required-region behavior;
  `tsc --noEmit`; `vite build`.
- End-to-end `verify` pass: seed a region, assign a division, submit a
  request over the L2 cap, approve as L1, confirm it lands with the region
  VP; submit as a sole L1 approver and confirm it escalates.

## Seed data

`backend/seed.py` gains one sample region wired to the seeded division(s) and
a VP user, so a fresh dev database can exercise L2 immediately.
