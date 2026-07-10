# Requests table sorting — design

**Date:** 2026-07-10 · **Status:** implemented

## Goal

Let users sort the requests table by clicking column headers, per Bryan's
request ("sort button at the top of my request table"). Chosen over a
filter-bar dropdown for familiarity and zero extra chrome.

## Design

- Sorting lives in the shared `RequestsTable` component
  (`frontend/src/routes/RequestsListPage.tsx`), so the Requests list and the
  Dashboard approvals table both get it.
- All five columns sortable: Number, Status, Division, Requestor, Total.
  First click = ascending, second = descending; clicking another column
  switches to it ascending. Active column shows a lucide Chevron (▲/▼);
  inactive headers reveal a faint chevron on hover. `aria-sort` set on the
  active `<th>`.
- Client-side only — rows are already fully loaded; no backend/API change.
- Comparators (`frontend/src/routes/requestsSort.ts`, unit-tested):
  - `total_cost`: numeric, null → 0.
  - `status`: workflow order (DRAFT → PENDING_L1/2/3 → APPROVED → REJECTED),
    not alphabetical.
  - text columns: `localeCompare`, blanks last in both directions.
- Default (no click yet): server order, unchanged from before.

## Verification

Vitest unit tests for the comparators; typecheck + build; driven live with
Playwright (Total asc/desc, column switch, status workflow order, aria-sort).
