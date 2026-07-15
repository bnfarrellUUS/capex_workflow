# Phase 2 — proposed enhancements (pending Finance review)

Five features Bryan selected on 2026-07-15, written up for the Finance group in
**`CAPEX Flow - Proposed Enhancements.docx`** (repo root; its closing section
also lists eight smaller later-phase candidate ideas). **Do not build until
Finance has reviewed and answered each section's "Questions for Finance"** —
their answers may change the rules below. Recommended order: 1 → 2 → rest in
any order; confirm with Bryan which feature to start with.

1. **Budget upload & tracking** — real annual CAPEX budgets per division
   (replacing the trust-based `budgeted` flag): admin uploads Excel/CSV
   (division number, amount) or edits amounts on an Admin → Budgets page;
   dashboard shows budget / spent (APPROVED) / committed (PENDING_*) /
   remaining per division; over-budget warnings on the wizard Review step and
   request detail page. Provisional rules: per-division per-calendar-year
   (request counts by `request_date` year), warn-only (no hard block),
   approved + pending both count. Implementation sketch: mirror the Divisions
   CRUD stack; new `DivisionBudget` model (unique division+year); the app's
   first aggregation query; `openpyxl` dep for .xlsx.
2. **Exports & reporting** — Export-to-Excel/CSV of the (filtered) requests
   list, plus a reports page: spend by division/month/status, cycle-time
   (avg days to approve). Build after #1 to reuse its summary plumbing.
3. **Reminders & escalation** — scheduled job emails the approver pool when a
   request sits at a level > N days (proposed 3), escalates after a second
   threshold (proposed 7); two new editable email templates + admin setting.
4. **Comment threads** — Q&A thread on the request detail page so approvers
   can ask questions without rejecting; immutable comments, email notification
   to the other party; request stays put in the workflow.
5. **Printable PDF of approved request** — Download-PDF button rendering the
   full request, approval history (names/dates), and finance breakdown for
   audit files / PO packages.

## Later-phase candidate ideas (awareness only, also in the docx)

1. Managed dropdown lists for equipment type/make and GL account
   (admin-maintained pick lists, "other/request new" escape hatch).
2. Vendor tracking & competitive bids (real bid records behind the
   `competitive_bids` flag).
3. Site/location on requests (location list per division; spend by site).
4. Duplicate-request warning at submission.
5. Microsoft 365 single sign-on (replaces default-password/reset/lockout).
6. Attachment upload guardrails — size cap + file-type allowlist
   (recommended soon regardless; today uploads accept any type/size).
7. Bulk approval from the pending list.
8. Read-only auditor role.
