# Exports & Reporting — design (2026-07-17)

Phase 2 feature #2 (`PHASE2-PROPOSALS.md`). Approved by Bryan 2026-07-17.
Built standalone — does not depend on feature #1 (budgets).

## Scope

1. **Export to Excel** of the (filtered) requests list — available to every
   user, exporting only the rows they can already see.
2. **Reports page** — FINANCE/ADMIN only: spend by division / month / status
   and cycle time (avg days to approve), per calendar year.

Decisions made during brainstorming:

- Format: **.xlsx only** (no CSV). New backend dep: `openpyxl`.
- Export depth: **fuller dump** — list columns plus dates, flags, economic
  fields, and the finance cost breakdown (one row per request, no line-item
  sheet).
- Reports UI: **tables + inline CSS bars** (no chart library).
- Report filter: **year picker** over `request_date` calendar year.
  **Spend = APPROVED only**; PENDING_* shown as a separate pipeline column.
- Generation is **server-side**; aggregation is computed **in Python** (small
  data volumes; avoids SQLite-vs-Azure-SQL dialect risk).
- Export sorts by request number (users re-sort in Excel).
- The requests list page gains an **"All" scope tab for ADMIN/FINANCE** (the
  API already supports `scope=all`; the UI never exposed it).

## Backend

### Export endpoint

`GET /api/requests/export.xlsx` on the existing `requests` blueprint; thin
route delegating to a new `app/services/export_service.py`.

- Query params: `scope`, `status`, `division_id` (same semantics as the list
  route — visibility comes from `request_service.list_requests`, so a
  non-ADMIN/FINANCE caller asking for `scope=all` silently gets their own
  requests, same as the list) plus `q`, which replicates the client-side
  search: case-insensitive contains over number, division display name
  (`{number} — {name}`), and requestor name.
- Rows sorted by request number. Workbook built with openpyxl; response is a
  download: `Content-Disposition: attachment;
  filename=capex-requests-<YYYY-MM-DD>.xlsx`.
- Columns (one row per request): Number, Status, Division, Requestor,
  Request Date, Total Cost, Current Level, Required Levels, Budgeted,
  Replacement, Health & Safety, Revenue Generating, Environmental,
  Competitive Bids, Lease Recommended, Asset Life, IRR After Tax,
  First-Year EBIT, Annual Savings, Payback Years, NPV Savings, Asset Number,
  GL Account, Useful Life (years/months), In-Service Date, each `cost_*`
  column, Finance Completed.
- Cell typing: money columns are numeric with a currency format; dates are
  real dates; flags render Yes/No. Header row styled brand navy
  (`#0B2A4A`, white bold text). Empty result still returns a valid workbook
  with the header row.

### Reports endpoint

New `app/blueprints/reports.py` (`/api/reports`) →
`GET /api/reports/summary?year=<yyyy>`, FINANCE-or-ADMIN only (403
otherwise), delegating to a new `app/services/report_service.py`.

- Loads the year's requests by `request_date` calendar year; aggregates in
  Python. `year` defaults to the current year.
- Response shape (money via `money_str`):

```json
{
  "year": 2026,
  "years": [2025, 2026],
  "totals": {"approved_total": "…", "approved_count": 0,
              "pending_total": "…", "pending_count": 0,
              "request_count": 0},
  "by_division": [{"division": "12 — Name", "approved_total": "…",
                    "approved_count": 0, "pending_total": "…",
                    "pending_count": 0}],
  "by_month": [{"month": 1, "approved_total": "…", "approved_count": 0,
                 "pending_total": "…", "pending_count": 0}],
  "by_status": [{"status": "APPROVED", "count": 0, "total": "…"}],
  "cycle_time": {"avg_days": 4.2, "count": 3}
}
```

- `years`: distinct `request_date` years present (for the picker), always
  including the requested year.
- Spend = APPROVED requests' `total_cost`; pipeline = `PENDING_L*`. DRAFT and
  REJECTED appear only in `by_status`. Requests with no division group under
  `"—"`. `by_month` always has 12 rows.
- `cycle_time`: over requests approved in the year — days from the first
  SUBMITTED `ApprovalAction` to the action that made the request APPROVED
  (its last APPROVED action); never-approved requests excluded; `avg_days`
  null when count is 0.

## Frontend

### Requests list (`RequestsListPage`)

- Scope toggle gains **"All"**, rendered only when `useMe()` includes ADMIN
  or FINANCE.
- **Export** button (secondary `Button`, `DownloadIcon` from `ActionIcons`)
  in the filter bar, visible to everyone. Downloads the export with the
  current `scope`/`status`/`q` via the API client as a blob (session cookie +
  error handling like other calls), saving with the server filename.
  Query-string building lives in a pure helper (unit-testable).

### Reports page (`routes/ReportsPage.tsx`, route `/reports`)

- Sidebar entry **Reports** — new `reports` icon in `NavIcons` (24px grid,
  rounded joins, `currentColor`), shown only for FINANCE/ADMIN; the route
  also guards and redirects others to the dashboard.
- One `BrandCard` (page pattern) with new `reports` mark.
- Header: year `Select` (from `years`, default current year) + `StatCard`
  strip: approved spend, pending pipeline, request count, avg days to
  approve.
- Sections, each a brand-styled table (sky-tint headers): **Spend by
  division**, **Spend by month**, **By status** — approved + pending columns,
  inline CSS horizontal bar (accent fill on `surface-2` track, width
  proportional to section max) beside each approved total.
- Data via TanStack Query keyed on year.

### API layer

- New `api/reports.ts`: `getReportSummary(year?)`.
- `api/requests.ts`: export URL helper + blob download function.

## Testing

Backend (pytest):
- Export: login required; requestor sees only own rows; `scope=all` as
  non-privileged falls back to own; `status`/`q` narrow rows; workbook parses
  (openpyxl) with expected headers, numeric Total Cost, finance `cost_*`
  values on an APPROVED request; empty export is a valid workbook.
- Reports: 403 for non-FINANCE/ADMIN; seeded fixture asserts approved vs
  pending split, month bucketing, status counts; cycle-time math; empty year
  returns zeroed sections; `years` correct.

Frontend (vitest + tsc):
- Export URL helper (drops empty params, encodes `q`).
- ReportsPage renders stats + tables from a mocked summary; year change
  refetches; non-finance redirect.
- List page: "All" tab hidden for plain requestor, shown for FINANCE.

## Docs & commits

Update CLAUDE.md (new blueprint/services, Reports page, nav mark) and mark
feature #2 built in `PHASE2-PROPOSALS.md`. Focused commits: backend export,
reports API, frontend list changes, Reports page, docs.
