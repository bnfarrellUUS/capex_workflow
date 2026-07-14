# Approval-history dates + editable finance cost breakdown

**Date:** 2026-07-14 · **Status:** approved by Bryan

## Problem

1. The request detail page lists approval actions without showing *when* each
   action happened, even though the API already returns `created_at` per action.
2. The finance cost-breakdown form is a dead end: it uses `type="number"`
   inputs (spinner arrows), starts blank instead of prefilled, disappears the
   moment it is saved, and the backend rejects any re-save
   (`"The Finance section is already completed."`). The saved values are never
   displayed anywhere on the detail page.

## Decisions (confirmed with Bryan)

- Finance users can edit and re-save the cost breakdown **anytime** on an
  approved request, including after it was marked complete.
- The saved breakdown is **visible read-only to all viewers** of an approved
  request; Finance users see editable fields instead.

## Design

### 1. Approval history table (frontend only)

Replace the `<ul>` in `RequestDetailPage.tsx` with a table styled like the
Equipment table: **Action | Level | By | Date | Comment**.

- Date renders `created_at` in the viewer's local timezone
  (`Jul 14, 2026, 9:32 AM` style). ISO strings without a timezone marker are
  treated as UTC (SQLite can round-trip the aware UTC datetimes naive).

### 2. Finance cost breakdown

**Backend** — `workflow_service.complete_finance`: drop the
`req.finance_completed` guard so a re-save succeeds. Each save still sets
`finance_completed = True` and logs a `FINANCE_COMPLETED` action, so edits
appear in the approval history with dates. Tests: re-save succeeds and updates
values; non-Finance still gets 403.

**Frontend** — `RequestDetailPage.tsx`:

- A **Finance cost breakdown** section renders for every request at
  `APPROVED` status (finance-completed or not), for all viewers.
- Non-Finance viewers: read-only values (em dash for empty), plus a
  "not completed yet" note when applicable.
- FINANCE users: editable plain-text inputs (`inputMode="decimal"`, no number
  spinners), **prefilled** from the saved `cost_*` values, with a Save button
  that works before and after completion.

## Verification

Backend `pytest -q`; frontend `tsc --noEmit` + `vite build`.
