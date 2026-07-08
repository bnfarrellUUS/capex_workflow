# CAPEX Tracking & Workflow Automation — Design

**Date:** 2026-07-08
**Status:** Approved by Bryan Farrell
**Replaces:** ContinuFlow (ContinuServe LLC), retiring ~August 2026

## 1. Purpose

Internal web application for United Uptime Services to submit, route, approve, and search capital expenditure (CAPEX) requests. Replaces the retiring ContinuFlow system. Approval workflow only — actual spend is tracked in the accounting system.

## 2. Requirements summary

| Requirement | Decision |
|---|---|
| Core scope | 6-step CAPEX request wizard + multi-level approval workflow |
| Approvals | 3 levels routed by dollar thresholds (Manager → VP/Director → CFO/CEO), thresholds admin-configurable |
| Login | App-managed username/password (no SSO) |
| Users | 25–100 |
| Hosting | Azure (App Service + Azure SQL Server + Blob Storage) |
| Databases | SQLite for local development; Azure SQL Server for test and production (via Prisma — avoid provider-specific features so both work identically) |
| Notifications | Email on assignment/decision + daily reminder job for stale approvals (default 3 days, configurable) |
| Attachments | Yes — quotes, bids, lease evaluations |
| History | Fresh start; no migration from ContinuFlow |
| Timeline | Flexible; quality over speed |

## 3. Architecture

```
Browser ──► Next.js 15 app (Azure App Service)
                │  React UI + API routes, one deployment
                ├──► Azure SQL Server (test & prod) / SQLite (dev) via Prisma
                ├──► Azure Blob Storage (attachments, app-mediated access)
                └──► Email via M365 SMTP relay (send-only mailbox, e.g. capex@uniteduptime.com)

Reminder job: daily scheduled task (App Service WebJob/cron) finds requests
pending > N days and emails the assignee. Notification log prevents double-sends.
```

- **Stack:** Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Prisma ORM, next-themes (light/dark mode)
- **Auth:** Auth.js (NextAuth) credentials provider — bcrypt password hashing, httpOnly/secure session cookies, login rate limiting with lockout, self-service password reset by email, admin reset
- **Environments:** local dev (SQLite) → test (Azure, Azure SQL Server) → production (Azure, Azure SQL Server).

## 4. Data model

- **User** — name, email, username, passwordHash, roles, division, active flag, delegate (userId, for out-of-office)
- **Division** — number, name
- **ApprovalThreshold** — 3 levels; each has a min/max dollar range and assigned approver. L1 approvers are assigned per division; L2 and L3 approvers are company-wide (VP/Director and CFO/CEO). Admin-editable.
- **CapexRequest** — auto-numbered `CX######`; all wizard fields:
  - Basic info: date, requestor, equipment/project description, division number/name, flags (budgeted, replacement equipment, health & safety driven, revenue generating, environmental/sustainability, competitive bids received, lease-recommended)
  - Brief description & justification (text)
  - Effect on operations (text)
  - Economic justification: asset/project life, IRR after tax, first-year EBIT, annual savings, payback years (auto-computed from total cost ÷ annual savings, overridable), NPV of future savings
  - Finance section: cost by category (Autos & Trucks, Machinery & Equipment, Improvements, Furniture & Fixtures, Permits, Misc) + total project cost
  - status, currentAssignee, timestamps
- **EquipmentItem** — request FK; units, new/used, type, make, model, cost. Line items auto-sum into request total.
- **Attachment** — request FK; filename, blob reference, contentType, size, uploadedBy, uploadedAt
- **ApprovalAction** — append-only audit trail: request FK, actor, actedForApprover (delegation), action (submitted / approved / rejected / resubmitted / finance_completed), comment, timestamp
- **NotificationLog** — request FK, recipient, type, sentAt

**Status flow:** `DRAFT → SUBMITTED → PENDING_L1 → PENDING_L2 → PENDING_L3 → APPROVED | REJECTED`
(Cross-database compatibility with SQLite and SQL Server: statuses stored as strings validated in app code, not DB enums.)

## 5. Roles & workflow

Roles (a user may hold several):

| Role | Capabilities |
|---|---|
| Requestor | Create/edit own drafts, submit, view own, resubmit rejected |
| Approver | Requestor + approve/reject assigned requests, set delegate |
| Finance | View all requests; complete cost-category section after final approval |
| Admin | Manage users, divisions, thresholds, approver assignments; view all |

Workflow rules:
1. On submit, total cost determines required levels (e.g., under L1 cap → one signature; above L2 cap → all three). Request assigned to the division's L1 approver.
2. Approval advances the request to the next required level, or marks APPROVED if final.
3. Rejection requires a comment → REJECTED, returned to requestor; requestor may edit and resubmit (restarts at L1; full history preserved).
4. If an approver has an active delegate, new assignments route to the delegate; audit trail records the actual actor and whom they acted for.
5. Every transition writes an ApprovalAction and sends an email.
6. **Finance completes the cost-category breakdown after final approval** (matches current form's "To Be Completed by Finance"). Request shows a "finance pending" flag until done.

## 6. Screens

1. **Login** — username/password; forgot-password via email
2. **Dashboard** — My Approvals queue, My Requests with statuses, recent activity, New Request button
3. **New Request wizard** — 6 steps mirroring ContinuFlow (Basic Info; Description & Justification; Effect on Operations; Equipment Requests; Economic Justification; Finance section visible read-only), auto request number, division auto-fill from profile, live cost summing, auto payback calc, Save Draft on every step, attachment upload
4. **Request detail** — all fields on one page; attachments; status pipeline visual; approval history with comments; Approve/Reject when assigned to viewer; Export PDF
5. **Search / All Requests** — filters (req #, requestor, division, status, date range), sortable table, Excel export
6. **My Rejected** — rejection reasons, revise & resubmit
7. **Admin** — users (create, deactivate, reset password, roles, division), divisions, thresholds & approver assignments
8. **Profile** — change password, set delegate

Styling: brand assets from `brand/` — palette navy `#0B2A4A`, blue `#2E6DF0` (primary accent), sky `#8FB2FF` (accent on dark); IBM Plex Sans typeface; logo mark `brand/aria-mark.svg` (currentColor, adapts to theme) and favicon `brand/aria-favicon.svg`. **Light and dark mode**, toggleable from the header (defaults to system preference, choice persisted). Clean modern UI, tablet-friendly.

## 7. Email notifications

- On assignment: "CX000245 is waiting for your approval" (link to request)
- On decision: requestor notified of approve/reject (with comment)
- On final approval: Finance notified to complete cost section
- Daily reminder for approvals pending > 3 days (configurable)
- All sends logged in NotificationLog; reminder job checks the log to avoid duplicates.

## 8. Security

- bcrypt password hashing; rate-limited login with account lockout
- Sessions: httpOnly, secure, sameSite cookies
- Every API route enforces role + ownership checks server-side
- Attachments served through app routes with access checks (no public blob URLs)
- All input validated server-side (zod schemas shared with client forms)

## 9. Error handling

- Optimistic-concurrency guard on approval actions (two people acting on the same request → second gets a clear "already actioned" message)
- Failed email sends are logged and retried by the daily job; email failure never blocks a workflow transition
- Draft autosave failures surface a visible "not saved" indicator

## 10. Testing

- **Unit (test-first):** workflow engine — threshold routing, level advancement, rejection/resubmission, delegation, finance-completion gating
- **Integration:** API routes — auth, role enforcement, request lifecycle, attachment access control
- **Manual smoke:** wizard end-to-end, email delivery, Excel/PDF export

## 11. Out of scope

- SSO / Entra ID (may be revisited later)
- Actual-spend tracking, budget-vs-actual rollups
- Data migration from ContinuFlow (Excel export kept as offline archive)
- Mobile app (responsive web only)
