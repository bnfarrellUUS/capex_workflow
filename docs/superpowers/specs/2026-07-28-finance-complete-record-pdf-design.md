# Finance-complete record email + request PDF — design

**Date:** 2026-07-28
**Status:** approved, ready for implementation plan
**Relation to roadmap:** delivers Phase 2 proposal **#5 (printable PDF of an
approved request)** from `PHASE2-PROPOSALS.md`, plus a new notification that
proposal did not include. Built at Bryan's direction ahead of the Finance
review that `CLAUDE.md` gates Phase 2 on — the same way #2 (exports &
reporting) was built on 2026-07-17.

## Problem

When Finance completes the cost breakdown, a request is finished — fully
approved, costed, and ready for the audit file. Nothing happens at that moment:
the requestor got an "approved" email earlier, before the finance numbers
existed, and there is no way to obtain a single document recording the whole
request.

Two deliverables:

1. A **PDF** of the complete request — details, approvals, finance breakdown.
2. A **final email to the requestor** when Finance first completes, with that
   PDF attached, for their records.

## Decisions

| Question | Decision |
| --- | --- |
| When does the email fire? | On the **first** completion only (`finance_completed` false → true). Re-saves send nothing. |
| Corrections after the first send? | A **manual "Resend record to requestor"** button for FINANCE/ADMIN. |
| Recipients | **The requestor only.** Approvers already received their own decision emails. |
| Download button? | **Yes** — on the request detail page, at **any status**. |
| Admin-hidden wizard sections | **Omitted from the PDF**, matching the detail page. |
| Existing data | Nothing is deleted or migrated; the PDF is generated on demand and never stored. |

## PDF generation

New dependency: **`reportlab>=4.0`** in `backend/requirements.txt`. Pure
Python, pip-installable, no system libraries. WeasyPrint was rejected despite
letting us reuse the email HTML: it needs GTK/Pango native libs on Windows,
which is where this app runs.

`backend/app/services/pdf_service.py`, split so the content logic is testable
without parsing PDF bytes:

- **`request_pdf_sections(req, hidden) -> list[dict]`** — pure; no reportlab
  import. Each entry is a section: `{"kind": "fields"|"text"|"table",
  "title": str, ...}` carrying already-formatted strings. Tests assert on this.
- **`render_pdf(sections) -> bytes`** — reportlab Platypus
  (`SimpleDocTemplate`, `Paragraph`, `Table`). One smoke test.
- **`build_request_pdf(req, hidden) -> bytes`** — composes the two.
- **`pdf_filename(req) -> str`** — `"CX000123.pdf"`.

### Contents, in order

1. **Brand header** — reuses `backend/app/assets/email_header.png` (the navy
   band with logo and wordmark). No new artwork.
2. **Title** — `Capital Request CX000123` plus the status.
3. **Summary** — requestor, division, request date, total cost.
4. **Basic info** — request date and the seven flags as Yes/No.
5. **Justification** — omitted when `description` is hidden.
6. **Effect on operations** — omitted when `effect_on_ops` is hidden.
7. **Asset details** — line-item table (units, condition, type, make, model,
   cost) plus the total. Omitted when `asset_details` is hidden.
8. **Economic analysis** — the six economic fields. Omitted when `economic` is
   hidden.
9. **Finance cost breakdown** — the six `cost_*` amounts plus asset number, GL
   account, useful life, in-service date. **Present only when
   `finance_completed` is true**, since before that there is nothing to show.
10. **Approval history** — action, level, by, date, comment for every
    `ApprovalAction`, dates rendered from UTC like the detail page.
11. **Attachments** — the filenames only (not the files). An audit record
    should state what was submitted with it. Always listed, because the detail
    page's Attachments section is likewise always visible.
12. **Footer** — generation date, "CAPEX Flow — United Uptime Services", and
    page numbers.

Section visibility uses the same keys as the wizard registry
(`description`, `effect_on_ops`, `asset_details`, `economic`), read from
`settings_service.get_hidden_sections()`.

## Download endpoint

`GET /api/requests/<id>/pdf` in `blueprints/requests.py`:

- `@login_required`, then `request_service.get_request(id, current_user)` — so
  it **inherits the detail page's exact visibility rule** (`_can_view`) with no
  new authorization logic. A viewer who cannot see the request gets its 403.
- Responds `application/pdf` with
  `Content-Disposition: attachment; filename="CX000123.pdf"`, mirroring the
  attachment-download route.
- Available at any status. A DRAFT's PDF simply has an empty approval history
  and no finance section.

Frontend: a **Download PDF** button on `RequestDetailPage` using the existing
`DownloadIcon`, rendered as a plain `<a href>` (same-origin, cookie auth) the
way attachment links already work. A new `pdfUrl(id)` helper joins
`attachmentUrl` in `api/requests.ts`.

## New email template: `FINANCE_COMPLETE`

A fifth editable template, added to `email_template_service`:

- `TYPES` gains `"FINANCE_COMPLETE"`.
- `NAMES`: `"Record complete"`.
- `TOKENS`: `_COMMON` (number, requestor, division, total_cost, link) — no new
  tokens needed.
- `DEFAULTS`:
  - subject: `"{number} is complete — your record copy"`
  - `body_html`: `"<p>Your request <strong>{number}</strong> ({total_cost}) is
    fully approved and the finance details are now complete.</p><p><br></p>
    <p>A PDF copy of the full request, its approvals, and the finance
    breakdown is attached for your records.</p>"` + `_FACTS`
  - Paragraphs and `<strong>` only, so Quill round-trips it unchanged — no
    tables, `bgcolor`, or VML.
- `email_frame.BUTTONS` maps it to the existing **`btn-approved`** asset, whose
  label is already the generic "View the request". **No new button PNG**, so no
  new artwork to review and no Pillow dependency.

Admins edit it under **Admin → Email Templates** exactly like the other four.
The list page, `TemplateTabs`, and editor are all driven off the API's type
list, so the fifth tab appears with **no frontend changes**.

## Attachment plumbing

`email_outlook.send(to, subject, body, html=None, attachments=None)` —
`attachments` is a list of `(filename, bytes)`. Outlook COM's
`Attachments.Add` takes a path, not bytes, so each attachment is written to a
temporary file, attached, and the temp files are removed in a `finally` after
`Send()` returns. Inline brand assets keep their existing Content-ID path;
these are ordinary visible attachments and get no Content-ID.

`notify._emit(...)` and `notify._send_template(...)` gain an `attachments`
passthrough defaulting to `None`, so every existing caller is unaffected.

New `notify.notify_finance_complete(req)`: builds the PDF via `pdf_service`,
then sends the `FINANCE_COMPLETE` template to `req.requestor.email` with
`[(pdf_filename(req), pdf_bytes)]` attached.

**Test mode is unchanged and still applies:** the message is redirected to the
test recipient with the usual banner, and the PDF rides along, so the
attachment can be checked safely before going Live.

## Trigger and resend

Notifications fire from the **blueprint**, matching every other notification in
the app (`workflow_service` stays email-free).

In `POST /api/requests/<id>/finance`, after `complete_finance` returns:

```
first = sum(1 for a in req.actions if a.action == "FINANCE_COMPLETED") == 1
if first:
    notify.notify_finance_complete(req)
```

Counting the audit actions detects the first completion **without changing
`complete_finance`'s signature and without an extra query** — the trail already
records every `FINANCE_COMPLETED`.

`POST /api/requests/<id>/resend-record`:

- `@require_roles("FINANCE", "ADMIN")`
- `ServiceError` 400 when the request is not `finance_completed` — there is no
  record to send yet
- calls the same `notify.notify_finance_complete(req)`
- returns the serialized request, like the other action routes

Frontend: a **Resend record to requestor** button beside Download PDF on
`RequestDetailPage`, shown only to FINANCE/ADMIN on a finance-complete
request, using the page's existing `act()` busy/error handling.

## Testing

Backend (`cd backend && pytest -q`):

- `request_pdf_sections`: Economic section absent when `economic` is hidden;
  Justification/Effect/Asset details likewise; finance section absent until
  `finance_completed`, present after; approval-history rows match the request's
  actions; flags render Yes/No.
- `render_pdf`: output starts with `%PDF-` and is non-trivial in size.
- `GET /api/requests/<id>/pdf`: owner 200 with
  `Content-Disposition` naming `CX…​.pdf` and an `application/pdf` type;
  unrelated user 403; anonymous 401.
- Trigger: first `POST /finance` sends exactly one `FINANCE_COMPLETE`
  notification to the requestor; a second `POST /finance` sends none.
- `resend-record`: FINANCE 200 and sends; REQUESTOR 403; 400 when not yet
  finance-complete.
- A spy on `email_outlook.send` asserts the PDF bytes and filename actually
  arrive as an attachment.
- `FINANCE_COMPLETE` appears in the templates API list and renders with its
  tokens substituted.

Frontend (`npm test`): Download PDF button present with the right href;
Resend button shown for FINANCE on a complete request and hidden for a plain
requestor. Existing `RequestDetailPage` mocks need the new query/route added.

Full gate afterwards: `pytest -q`, `node ./node_modules/typescript/bin/tsc
--noEmit -p tsconfig.json`, `node ./node_modules/vite/bin/vite.js build`.

**Manual verification (required, not optional):** send a real `[SAMPLE v1]` to
Bryan in classic Outlook and iterate on his screenshots — per the project's
email-verification workflow, browser previews do not prove an Outlook render.
Confirm the attachment opens, the PDF's own layout is right, and the body
renders correctly.

## Docs

`CLAUDE.md`: the new `pdf_service`, the `/pdf` and `/resend-record` routes, the
fifth email template type, `email_outlook.send`'s `attachments` parameter, and
the finance-complete trigger rule (first completion only, plus manual resend).
`PHASE2-PROPOSALS.md`: mark #5 as built, with a pointer to this spec.
