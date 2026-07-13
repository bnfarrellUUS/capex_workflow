# Attachments step in the request wizard

**Date:** 2026-07-13

## Context

Attachments can currently only be added on a request's detail page, after the
draft exists. With draft creation now deferred to first save, users want to
attach documents during creation, inside the wizard. Add a dedicated
**Attachments** step; uploading a file on a brand-new request lazily creates the
draft first (same pattern as Save Draft/Submit), then attaches.

## Behavior

- Wizard steps become 7: Basic Info, Description, Effect on Ops, Equipment,
  Economic, **Attachments**, Review.
- The Attachments step lists the request's current attachments (each with a
  **Remove**) and a file picker + **Upload**.
- **Upload:** `persist()` (create the draft if new + save the form) → get the id
  → `uploadAttachment(id, file)`. For a new request, after success navigate to
  `/requests/:id/edit` (preserving the step via location state) so the wizard is
  now editing the saved draft; the uploaded file appears in the list.
- **Remove:** `deleteAttachment(id, attId)` (only possible once the draft
  exists). Both upload and remove update the cached request so the list
  refreshes in place.
- The **Review** step shows the attachment count.
- Backend/API unchanged — reuses `uploadAttachment` / `deleteAttachment`
  (`POST`/`DELETE /api/requests/:id/attachments`), which already require the
  request be the owner's DRAFT/REJECTED. No file-type/size restriction is added
  (matches today's detail-page behavior).

## Frontend (`routes/WizardPage.tsx`)

- Add `'Attachments'` to `STEPS` before `'Review'`.
- Import `uploadAttachment`, `deleteAttachment`; add `useQueryClient`.
- `upload` mutation: `mutationFn(file)` → `const theId = await persist();
  return { id: theId, updated: await uploadAttachment(theId, file) }`;
  `onSuccess` → `qc.setQueryData(['request', id], updated)` and, if new,
  `navigate('/requests/:id/edit', { replace, state: { step } })`.
- `removeAttachment` mutation: `deleteAttachment(id, attId)` → `setQueryData`.
- New `Attachments` step component (file input ref + Upload button + list with
  Remove), reading `data?.attachments ?? []`; disabled while a mutation is
  pending. Uses the existing `UploadIcon` / `DownloadIcon` / `DeleteIcon`.

## Testing (`WizardPage.test.tsx`)

- Add `uploadAttachment`/`deleteAttachment` to the requests mock.
- New request: navigating to the Attachments step shows the Upload control;
  uploading a file calls `createDraft` then `uploadAttachment('new-1', file)`.
- Existing draft: uploading calls `uploadAttachment(routeId, file)` (no create).
- Keep all current wizard tests green. Then `tsc`, full vitest, `vite build`,
  and a visual check (attach during creation; file persists).

## Out of scope
File type/size limits; drag-and-drop; attaching after submission.
