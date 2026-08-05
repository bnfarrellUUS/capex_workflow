# Request comments — design

**Date:** 2026-08-05
**Status:** approved, ready for an implementation plan
**Origin:** Phase 2 proposal #4 ("Comment threads") in `PHASE2-PROPOSALS.md`

## Problem

An approver's only ways to respond to a request are **Approve** and **Reject**.
When something needs clarifying — "is this a replacement or an add?", "where are
the competitive bids?" — the approver either rejects the request (heavy-handed:
it drops out of the workflow and the requestor has to resubmit through the
wizard) or leaves the app entirely and sends an email. Neither leaves a record
on the request.

## Solution

A comment thread on the request detail page. Any comment is a **pure side
conversation**: it changes no status, no assignee, and no queue. The request
stays exactly where it is, with the same approvers, while the question and
answer are recorded against it. The approver then approves or rejects as
normal.

Explicitly **not** in scope: a "needs info" workflow state, editing or deleting
comments, @-mentions, attachments on comments, unread counts or badges.

## Data model

New model `RequestComment` in `backend/app/models/__init__.py`, one Alembic
migration:

| column | type | notes |
| --- | --- | --- |
| `id` | `String(36)` PK | uuid hex, `default=_id`, like every other table |
| `request_id` | FK → `capex_requests.id` | `ondelete="CASCADE"` |
| `author_id` | FK → `users.id` | `ondelete="NO ACTION"`, like `ApprovalAction.actor_id` |
| `body` | `Text` | |
| `created_at` | `DateTime` | naive UTC via `_utcnow`, like `ApprovalAction` |

`CapexRequest` gains `comments: Mapped[list["RequestComment"]]` with
`cascade="all, delete-orphan"`, so deleting a draft still works and takes its
comments with it.

Comments are **immutable**: no `updated_at` column, and no update or delete
route exists. The thread is a record, not a wiki.

## Backend

### Service — `backend/app/services/comment_service.py`

```
add_comment(request_id, viewer, body) -> RequestComment
```

Authorization is delegated to `request_service.get_request(request_id, viewer)`
— the same rule that governs the detail page, so "if you can see the request,
you can comment on it" needs no second rule to keep in sync. The body arrives
already stripped and length-checked by the schema; the service adds, commits,
and returns the row.

No `list_comments` function: comments ride along on `request_out` (below), so
there is nothing to list separately.

### Schema — `backend/app/schemas/request.py`

```python
class CommentIn(BaseModel):
    body: Annotated[str, StringConstraints(
        strip_whitespace=True, min_length=1, max_length=4000)]
```

A **type constraint, not a raising `field_validator`** — deliberately, because
of the known app-wide bug where a validator that raises produces a 500 instead
of a 400 (see CLAUDE.md → Conventions & gotchas). This shape returns a proper
400.

### Route — `backend/app/blueprints/requests.py`

```
POST /api/requests/<request_id>/comments   @login_required
```

Validates with `CommentIn`, calls `comment_service.add_comment`, then fires
`notify.notify_comment(req, comment)` — notifications fire from blueprints,
never from services, matching the existing convention. Returns `200` with the full
`request_service.request_out(req)` so the page refreshes from one response,
the same way the attachment routes work.

### Serialization — `request_service.request_out`

Adds:

```json
"comments": [
  {"id": "...", "body": "...", "author_id": "...",
   "author_name": "Dana Ruiz", "created_at": "2026-08-05T14:22:00"}
]
```

Oldest first (`sorted` by `created_at`, then `id` as a tiebreaker, matching how
`actions` is already sorted).

### Visibility fix — `request_service._can_view`

`_can_view` today allows only the requestor, the single `assignee_id`, FINANCE,
and ADMIN. Because a pending request belongs to a **pool** of eligible
approvers and `assignee_id` is only a display hint (the first of the pool), a
second pool approver sees the request on their "assigned" worklist, clicks it,
and gets a 403 — even though `workflow_service.approve` would accept their
decision. This is a pre-existing bug, and it would block exactly the people
this feature is for.

Fixed here:

```python
def _can_view(req, viewer):
    if viewer.id in (req.requestor_id, req.assignee_id):
        return True
    roles = viewer.roles_list
    if "ADMIN" in roles or "FINANCE" in roles:
        return True
    if req.status.startswith("PENDING_L"):
        from app.services import threshold_service, workflow_service
        actors = workflow_service.eligible_actors(
            req.current_level, req.division, threshold_service.list_thresholds())
        return viewer.id in {u.id for u in actors}
    return False
```

Imported inside the function, matching how `list_requests` and `request_out`
already avoid the circular import between `request_service` and
`workflow_service`.

Note the knock-on effect, which is correct and intended: this also unblocks the
detail page, the PDF download, and attachment downloads for pool approvers,
since all three route their authorization through `get_request`.

## Email

A sixth editable template, following the existing five exactly.

- `email_template_service.TYPES` gains `"COMMENT"`; `NAMES["COMMENT"] = "New comment"`.
- `TOKENS["COMMENT"] = _COMMON + [{author}, {comment}]`.
- `email_frame.BUTTONS["COMMENT"] = ("btn-approved", 162, 44, "View the request")`
  — **no new baked artwork**: that PNG's label already reads "View the
  request". (Per CLAUDE.md, new artwork is needed only for a new CTA label.)
- `sample_context` gains an `{author}` sample so the admin preview renders.

Shipped default:

- **Subject:** `New comment on {number}`
- **Body:** `<p><strong>{author}</strong> commented on request
  <strong>{number}</strong> ({total_cost}).</p><p><br></p>
  <blockquote>{comment}</blockquote>` + the standard `_FACTS` block.

Quill-safe: paragraphs, bold, and blockquote only — the same vocabulary the
other templates use.

### Recipients — `notify.notify_comment(req, comment)`

Notifies **the other side of the conversation**, deduped by email, never the
author:

| Author | Recipients |
| --- | --- |
| The requestor | Whoever is holding the request: the eligible approver pool at the current level while `PENDING_L*`; every active FINANCE user once `APPROVED`; **nobody** while `DRAFT` or `REJECTED` (nobody is waiting on it) |
| Anyone else (approver, FINANCE, ADMIN) | The requestor |

Delivery goes through the existing `_send_template`, so the Test/Live delivery
mode, the redirect banner, `EMAIL_ENABLED`, and the per-template `enabled` flag
all apply unchanged. `NotificationLog.type` is `"COMMENT"`.

## Frontend

### `components/CommentThread.tsx` (new)

`RequestDetailPage.tsx` is already 487 lines; the thread gets its own file.

Props: `{ req: CapexRequestData; onPosted: (updated: CapexRequestData) => void }`.

Renders each comment as author name + local timestamp + `whitespace-pre-wrap`
body, then a textarea and a **Post comment** button (disabled while empty or
in-flight). Timestamps reuse the detail page's UTC-aware `formatActionDate`
helper, which moves to a shared spot both files import rather than being
duplicated. Empty state: "No comments yet."

Styling uses the semantic tokens (`surface-2`, `border`, `muted`), not
hard-coded slate.

### `RequestDetailPage.tsx`

Renders `<CommentThread>` as its own section immediately after the approval
history table. Posting returns the updated request, which is written into the
TanStack Query cache for `['request', id]` — the same pattern the attachment
and finance actions already use.

The section shows at **every** status, including DRAFT and APPROVED — like the
detail page's Attachments section, it deliberately ignores the hidden-wizard-
sections config, because it is not a wizard step.

### `components/ActionIcons.tsx`

One new `CommentIcon` in the house style (24px grid, rounded joins,
`currentColor`), used as the section heading glyph and on the post button.

### `api/requests.ts`

```ts
export interface RequestComment {
  id: string; body: string
  author_id: string; author_name: string | null
  created_at: string | null
}
```

added to `CapexRequestData` as `comments: RequestComment[]`, plus:

```ts
export function addComment(id: string, body: string): Promise<CapexRequestData>
```

Existing `RequestDetailPage` test mocks build full `CapexRequestData` objects,
so they each need `comments: []` added.

## Record PDF

`pdf_service.request_pdf_sections` gains a **Comments** section immediately
after Approval history:

- `kind: "table"`, header row `["By", "Date", "Comment"]`, one row per comment
  in chronological order, dates via the existing `_datetime` helper.
- `empty_note: "No comments."` when there are none.

Built as plain dicts like every other section, so the content rule is testable
without parsing PDF bytes. `render_pdf` needs no change — it already handles
`kind: "table"`.

## Testing

**Backend** — new `backend/tests/test_comments.py`:

1. Requestor posts a comment → the returned payload contains it; status,
   `assignee_id`, and `current_level` are unchanged (the core promise of the
   feature).
2. Whitespace-only body → 400, not 500.
3. Over 4000 characters → 400.
4. A user with no relationship to the request → 403 on post.
5. A pool approver who is *not* `assignee_id` can view and comment (the
   `_can_view` fix).
6. Requestor comments while `PENDING_L2` → every eligible L2 approver is
   emailed, the requestor is not.
7. An approver comments → only the requestor is emailed.
8. Requestor comments on an `APPROVED` request → active FINANCE users are
   emailed.
9. Requestor comments on a `DRAFT` → nobody is emailed, and the comment still
   saves.
10. Deleting a draft with comments succeeds (cascade).

Any test spying on `email_outlook.send` must accept the `attachments=` kwarg,
per the existing convention.

**Backend, existing files** — a `request_pdf_sections` case asserting the
Comments section and its empty note; the `_can_view` change re-run against the
existing request/attachment/PDF authz tests.

**Frontend** — a vitest for `CommentThread`: renders existing comments, the
button is disabled on an empty box, posting calls `addComment` and clears the
box.

Full gate before commit: `cd backend && pytest -q`, then
`node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`,
`node ./node_modules/vitest/vitest.mjs run`, and
`node ./node_modules/vite/bin/vite.js build` from `frontend/`.

## Docs to update on completion

- `CLAUDE.md` — the data model list, the roles/workflow section (comments are a
  third response available to an approver), the email-template count (five →
  six) and its `COMMENT` type, and the detail-page description.
- `PHASE2-PROPOSALS.md` — mark item 4 built, with a pointer to this spec.
