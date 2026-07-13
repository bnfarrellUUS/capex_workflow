# Defer draft creation to first save

**Date:** 2026-07-13

## Context

Clicking **New Request** navigates to `/requests/new`, whose `NewRequestPage`
immediately POSTs `createDraft()` and redirects to the id-keyed wizard. So
merely opening the screen (and leaving) leaves an empty `$0` DRAFT in the
database — the list is now full of them. A draft should be created only when
the user actually saves.

## Behavior (confirmed)

- Opening New Request creates nothing. **Next** and **stepper** clicks navigate
  locally without saving. The draft is created on the first **Save Draft** or
  **Submit**.
- For an already-saved draft (the `/requests/:id/edit` route), Next/stepper keep
  auto-saving as they do today — that only updates an existing draft and guards
  against losing edits.

## Frontend

- **Remove `NewRequestPage`.** Route `/requests/new` renders `WizardPage`
  directly (no id).
- **`WizardPage` gains a "new" mode** (`useParams` has no `id`):
  - Seeds a blank form from `wizard/types.ts` `blankForm(divisionId, date)` —
    division prefilled from the current user, date = today, requestor shown from
    `useMe`, header title "New Request" (no number yet).
  - The `getRequest` query is `enabled` only when there is a route id.
  - **Next / stepper:** in new mode call `setStep` directly (no persist); in
    edit mode keep `saveThen(...)`.
  - **Save Draft:** if new, `createDraft()` → `updateDraft(newId, payload)` →
    `navigate('/requests/:id/edit', { replace, state: { step } })` so it becomes
    a normal saved draft (step preserved across the route change via location
    state); if editing, `updateDraft(id, payload)` as today.
  - **Submit (Review step):** one action — if new, `createDraft()` →
    `updateDraft(newId, payload)` → `submitRequest(newId)`; if editing, save then
    `submit`/`resubmit` (the existing REJECTED branch). Then navigate to
    `/requests/:id`. Submit no longer routes through `saveThen` (avoids a
    mid-flow remount).
  - `isRejected`, display number/requestor, and the `if (!form) …` loading guard
    updated to tolerate absent `data` in new mode.
- **`api/auth.ts`**: add `division_id` to `CurrentUser`.

## Backend

- Add `division_id` to `_user_json` in `blueprints/auth.py` so the new form can
  prefill the requestor's division (matches the old server-side prefill). No
  model/migration change; `create_draft`/`update_draft` unchanged.

## One-time cleanup

- Delete existing **empty** DRAFTs: `status == "DRAFT"`, no equipment items,
  `total_cost` in (None, 0), blank `description`/`justification`/
  `effect_on_operations`, and no attachments. Run as a one-off script against
  the dev DB (`backend/instance/capex_dev.db`); print the count and the numbers
  before deleting. Drafts with any real content (e.g. CX000001/CX000002) are
  kept.

## Testing

- Frontend (`vitest`, extend `WizardPage.test.tsx`): rendering `/requests/new`
  does **not** call `createDraft`; clicking **Next** does **not** call
  `createDraft`; **Save Draft** calls `createDraft` then `updateDraft`; **Submit**
  from a new request calls `createDraft` → `updateDraft` → `submitRequest`. Keep
  the existing edit-mode + resubmit tests green.
- Backend (`pytest`): `/api/auth/me` includes `division_id`.
- Regression: `tsc`, full vitest, `pytest`, `vite build`; visual check that
  opening New Request and leaving creates no draft, and that Save Draft/Submit
  do.

## Out of scope
Changing edit-mode auto-save; a navigation "unsaved changes" guard.
