# CAPEX Flow — Standard Operating Procedure

**Application:** CAPEX Flow (United Uptime Services)
**Purpose:** Submit, route, approve, and complete capital-expenditure (CAPEX) requests.
**Audience:** Requestors, Approvers, Finance, and Administrators.
**Last updated:** 2026-07-09

---

## 1. Overview

CAPEX Flow is an internal web app that takes a capital-expenditure request from
**draft → multi-level approval → finance completion**. The number of approval
levels a request must clear is decided automatically by its **total cost**. Each
approval level has a **pool of eligible approvers**, and **any one member of the
pool** can act on the request.

Access the app at **http://localhost:5000** (dev). Dev admin login is
`admin / ChangeMe123!`.

---

## 2. Roles

A single user may hold more than one role.

| Role | Can do |
|------|--------|
| **REQUESTOR** | Create a draft, fill in the 6-step wizard, submit, and resubmit their own rejected requests. |
| **APPROVER** | Approve or reject requests currently assigned to a level whose approver pool they belong to. |
| **FINANCE** | After a request is fully approved, complete the finance cost breakdown. Can also view all requests. |
| **ADMIN** | Manage users, divisions, and approval thresholds. Can view all requests. |

**Delegate (out-of-office):** Every user may name a `delegate`. When an approver
has a delegate set, the system routes their approvals to the delegate instead.
The audit trail records that the delegate **acted for** the original approver.

---

## 3. The request lifecycle (status flow)

```
DRAFT ──submit──► PENDING_L1 ──approve──► PENDING_L2 ──approve──► PENDING_L3 ──approve──► APPROVED ──finance──► (finance_completed)
                      │                        │                        │
                      └──────── reject ────────┴──────── reject ────────┘
                                               ▼
                                           REJECTED ──resubmit──► PENDING_L1
```

- **DRAFT** — being written by the requestor. Editable.
- **PENDING_L1 / L2 / L3** — awaiting a decision at that level. Only levels that
  the total cost requires are used (see §4).
- **APPROVED** — cleared all required levels. Now waiting on Finance.
- **REJECTED** — a side state. The requestor (and only the requestor) may edit
  and **resubmit**, which sends it back to PENDING_L1 from the start.

> A request is only editable while in **DRAFT** or **REJECTED** status. Once
> submitted, requestors cannot change it.

---

## 4. How the number of approval levels is decided

When a request is submitted, the app sums the cost of all equipment line items
into **`total_cost`**, then compares it against the **Approval Thresholds** to
decide `required_levels`.

**Default seeded thresholds:**

| Level | Max amount | Meaning |
|-------|-----------|---------|
| **L1** | $50,000 | Requests up to $50k need **1** level of approval. |
| **L2** | $250,000 | Requests from $50,001–$250,000 need **2** levels. |
| **L3** | *(no cap)* | Requests above $250,000 need **3** levels. |

Rule: the required level is the **lowest level whose cap is ≥ the total cost**
(the top level has no cap and catches everything above). A request always starts
at L1 and steps up one level per approval until it reaches `required_levels`,
then becomes APPROVED.

> Thresholds are configurable by an Admin under **Admin → Approval Thresholds**.
> Changing the caps changes how future submissions are routed.

---

## 5. Who approves at each level (the approver pool)

Each level draws its eligible approvers from a different place:

- **Level 1** — the **division's L1 approver pool** (`Division.l1_approvers`).
  Set per division under **Admin → Divisions**.
- **Level 2 and Level 3** — the **threshold's approver pool**
  (`ApprovalThreshold.approvers`). Set under **Admin → Approval Thresholds**.

Each configured approver is then mapped through their **delegate** (if any) to
produce the list of people who may actually act. **Any one** of them can approve
(which advances the request) or reject.

- The request appears on the **"Assigned to me"** worklist of *every* eligible
  approver at the current level.
- `assignee_id` is only a display hint — it names the first approver in the pool,
  but any pool member may act.
- Two approvers can't both act: the transition is guarded, so a second action on
  an already-decided request returns a "already actioned by someone else" error.

---

## 6. Step-by-step procedures

### 6.1 Requestor — create and submit

1. **New Request** — creates a draft and opens the 6-step wizard.
2. Complete the wizard steps (step tabs are clickable and save as you go):
   1. **Basic Info** — division, flags (budgeted, replacement, health & safety,
      revenue-generating, environmental, competitive bids, lease recommended).
   2. **Description**
   3. **Effect on Operations** — justification, effect on operations.
   4. **Equipment** — line items (units, condition, type, make, model, cost).
      **At least one line item with a cost > 0 is required to submit.** The sum
      becomes the total cost that drives routing.
   5. **Economic** — asset life, IRR, first-year EBIT, annual savings, payback,
      NPV.
   6. **Review** — check everything, then **Submit**.
3. On submit the request moves to **PENDING_L1** and the L1 approver pool is
   notified (see §7).

**Prerequisites for a successful submit** (otherwise you get an error):
- At least one equipment line item with a positive cost.
- A division is set on the request.
- The division has at least one L1 approver configured.

### 6.2 Approver — approve or reject

1. Open a request from **"Assigned to me"** (or the dashboard approvals table).
2. **Approve** — optional comment. The request advances to the next required
   level, or becomes **APPROVED** if this was the last required level.
3. **Reject** — **a comment is required.** The request moves to **REJECTED** and
   the requestor is notified.

### 6.3 Requestor — resubmit a rejected request

1. Open the rejected request (it's editable again).
2. Fix what the rejection comment called out.
3. **Resubmit** — routing is recomputed from scratch and the request re-enters
   **PENDING_L1**.

### 6.4 Finance — complete the cost breakdown

1. After a request is **APPROVED**, all Finance users are notified it's pending.
2. Open the request and fill in the finance cost breakdown:
   autos/trucks, machinery, improvements, furniture, permits, misc.
3. **Complete** — sets `finance_completed`. This can only be done once, only by a
   Finance user, and only on an APPROVED request.

---

## 7. The notification ("email") process

### 7.1 When notifications fire

Notifications are triggered by the request routes at each transition:

| Event | Who is notified | Notification type |
|-------|-----------------|-------------------|
| **Submit** (draft → PENDING_L1) | Every eligible approver in the **L1 pool** | `ASSIGNED` |
| **Approve, not yet final** (advances to next level) | Every eligible approver in the **next level's pool** | `ASSIGNED` |
| **Approve, final** (→ APPROVED) | The **requestor** | `DECIDED` |
| **Approve, final** (→ APPROVED) | **All active Finance users** | `FINANCE_READY` |
| **Reject** (→ REJECTED) | The **requestor** | `DECIDED` |
| **Resubmit** (→ PENDING_L1) | Every eligible approver in the **L1 pool** | `ASSIGNED` |

Recipients are always resolved through the **delegate** mapping — an approver
who is out of office and has a delegate set will have their delegate notified
instead.

Notifications are **best-effort**: a notification failure is caught and logged
and will **never** block or roll back the workflow transition itself.

**Email content.** Each notification body includes the request details
(requestor, division, total cost) and a **deep link straight to the request in
the app** — the approver clicks it and lands on the request detail page where
the Approve / Reject buttons are. There is no approve-from-email; the link takes
them into the app to act. The link is built from the **`APP_BASE_URL`** config,
so set that to the real hostname when you move to a server. Example approver
email:

```
Subject: Action needed: CX000042 awaiting your Level 2 of 3 approval

Request CX000042 needs your Level 2 of 3 approval.

Requested by: Dana Ruiz
Division:     12 — Field Services
Total cost:   $182,400.00

Review and approve:
http://localhost:5000/requests/<id>
```

### 7.2 Current state: sent through local Outlook (redirected for testing)

For every notification the app **always**:
1. Writes a log line (`EMAIL to=… subject=…`) to the server log, and
2. Records a row in the **`NotificationLog`** table (recipient, type, request).

When **`EMAIL_ENABLED`** is on (the default in dev), it **additionally sends the
message through the Outlook desktop app** installed and signed-in on the machine
running the app (`backend/app/services/email_outlook.py`, via COM automation).
No SMTP credentials or Azure app registration are needed — the mail goes out as
the signed-in Outlook account.

> **⚠️ Redirected while testing.** Every message is currently **redirected to
> `EMAIL_REDIRECT_TO`** (default `bryan.farrell@uniteduptime.com`) instead of the
> real recipient. The intended recipient is written at the top of the body as
> `[Intended recipient: …]`. This lets you exercise the full flow without
> emailing real approvers. To deliver to real recipients, set the config value
> `EMAIL_REDIRECT_TO` to empty.

**Configuration** (env vars, read in `backend/app/config.py`):

| Var | Default (dev) | Meaning |
|-----|---------------|---------|
| `EMAIL_ENABLED` | `1` (on) | Set `0` to log/record only and not send. |
| `EMAIL_REDIRECT_TO` | `bryan.farrell@uniteduptime.com` | Where all mail is sent during testing. Clear it to send to real recipients. |
| `APP_BASE_URL` | `http://localhost:5000` | Base URL used for the deep link in every email. Set to the real hostname on the server. |

**Requirements to actually send:**
- Runs on a **Windows** machine with the **Outlook desktop app** installed and a
  profile signed in.
- `pywin32` is installed (in `requirements.txt`, Windows-only).
- Delivery is **best-effort**: if Outlook isn't available the failure is logged
  and the workflow transition still succeeds; the `NotificationLog` row is still
  written.

**When the app moves to a server** (developer task): the Outlook desktop backend
won't work headless. Replace `backend/app/services/email_outlook.py` with an
**SMTP** or **Microsoft Graph** backend. That module is the only place delivery
lives — `notify.send_email()` and all the recipient/routing logic above stay
unchanged.

### 7.3 Editing the emails (Admin → Email Templates)

Admins can customize all four emails without code changes under **Admin → Email
Templates**. For each email type you can edit the **subject**, the **body** (a
WYSIWYG rich-text editor — fonts, sizes, colors, lists, links), and an
**enabled** toggle (turn an email type off). A right-hand **placeholders** panel
lists the `{tokens}` available for that email (e.g. `{number}`, `{requestor}`,
`{division}`, `{total_cost}`, `{link}`, plus `{level}` for the approval email
and `{comment}` for the rejection email); click one to insert it at the cursor.
Tokens are replaced with real values when the email is sent.

Every email is wrapped in a fixed **brand frame** (navy header with the
Capital-Cycle logo mark, "United Uptime Services / CAPEX Flow", centered white
card, brand colors) so all four stay on-brand, and the editor shows the same
frame around the body while you type. The rounded header, the action button,
and the card's bottom edge are **inline images** (classic Outlook cannot draw
rounded corners from CSS), attached automatically to each email; the in-app
Preview shows the exact same HTML and images as the sent email. Recipients
whose mail client blocks pictures see the text alternative until they allow
images. Buttons:
**Save** (update the live template), **Save as Default** (capture the current
version as your baseline), **Preview** (see it rendered with sample data), and
**Reset to default** (revert to your saved baseline, or the shipped default if
none was captured).

---

## 8. Administration

Under **Admin** (ADMIN role required):

- **Users** — create/edit users, assign roles, set a user's division and
  out-of-office delegate. A user can't be deleted while they are still a required
  approver or have open requests (the error names the blockers).
- **Divisions** — create divisions and set each division's **L1 approver pool**
  (dual-listbox picker). These are the level-1 approvers for that division's
  requests.
- **Approval Thresholds** — set the **max amount** for L1/L2/L3 and the **L2/L3
  approver pools**. These caps decide how many approval levels each request
  needs (§4).
- **Email Templates** — customize the subject, body, and enabled state of the
  four notification emails, with `{token}` placeholders and a brand frame (§7.3).

**Setup checklist for a working workflow:**
1. Create divisions and assign each an **L1 approver pool**.
2. Set the **threshold caps** and the **L2/L3 approver pools**.
3. Create users with the right roles and divisions; set delegates as needed.
4. Confirm at least one active **Finance** user exists (they receive the
   post-approval hand-off).

---

## 9. Audit trail

Every action is recorded in **`ApprovalAction`** and shown on the request detail
page: `SUBMITTED`, `APPROVED`, `REJECTED`, `RESUBMITTED`, `FINANCE_COMPLETED`,
each with the level, actor, optional comment, and — for delegated actions —
whom the actor **acted for**. This is the system of record for who did what and
when.

---

## 10. Quick reference — key files (for developers)

| Concern | File |
|---------|------|
| Approval routing / level logic / transitions | `backend/app/services/workflow_service.py` |
| Notification recipients & delivery gate | `backend/app/services/notify.py` |
| Outlook COM send backend ("for now") | `backend/app/services/email_outlook.py` |
| Email config (`EMAIL_ENABLED`, `EMAIL_REDIRECT_TO`) | `backend/app/config.py` |
| Draft create/edit, serialization | `backend/app/services/request_service.py` |
| Threshold caps & pools | `backend/app/services/threshold_service.py` |
| HTTP routes (where notifications are triggered) | `backend/app/blueprints/requests.py` |
| Seeded default thresholds | `backend/seed.py` |
