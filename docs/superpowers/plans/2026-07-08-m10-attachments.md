# M10 — Attachments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Upload / download / delete file attachments (quotes, bids, lease evals) on a request, served only through access-checked routes.

**Architecture:** A `StorageDriver` interface with a local-disk driver for dev (Azure Blob later). `attachment_service` enforces access (upload/delete = owner while DRAFT/REJECTED; download = anyone who can view). Files stream through Flask routes — never a public URL. The detail page gets an attachments section.

**Tech Stack:** Flask, SQLAlchemy, React, pytest. Builds on M1–M9.

## Global Constraints
- Inherits all prior constraints. Files served only via `/api/requests/<id>/attachments/<attId>` with an access check (design §8). Dev storage under `backend/instance/uploads/` (gitignored). Upload/delete only by the requestor while DRAFT/REJECTED.

---

### Task 1: Storage adapter + attachment service + serialization

**Files:**
- Create: `backend/app/services/storage.py`
- Create: `backend/app/services/attachment_service.py`
- Modify: `backend/app/config.py` (add `UPLOAD_ROOT` for tests)
- Modify: `backend/app/services/request_service.py` (`request_out` → `attachments`) + expose `can_view`
- Test: `backend/tests/test_attachment_service.py`

- [ ] **Step 1: Failing tests** — `backend/tests/test_attachment_service.py`:
```python
import pytest
from app.services.errors import ServiceError
from app.services import attachment_service, request_service
from tests.factories import make_user, make_division


def _draft(owner):
    return request_service.create_draft(owner)


def test_add_and_get_attachment(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _draft(owner)
    att = attachment_service.add_attachment(req.id, owner, "quote.pdf", "application/pdf", b"hello")
    fetched, data = attachment_service.get_attachment(att.id, owner)
    assert data == b"hello" and fetched.filename == "quote.pdf" and fetched.size == 5


def test_upload_owner_only(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    other = make_user("other", roles='["REQUESTOR"]')
    req = _draft(owner)
    with pytest.raises(ServiceError):
        attachment_service.add_attachment(req.id, other, "x.pdf", "application/pdf", b"x")


def test_download_denied_for_stranger(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    stranger = make_user("stranger", roles='["REQUESTOR"]')
    req = _draft(owner)
    att = attachment_service.add_attachment(req.id, owner, "q.pdf", "application/pdf", b"x")
    with pytest.raises(ServiceError):
        attachment_service.get_attachment(att.id, stranger)


def test_delete_attachment(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _draft(owner)
    att = attachment_service.add_attachment(req.id, owner, "q.pdf", "application/pdf", b"x")
    attachment_service.delete_attachment(att.id, owner)
    with pytest.raises(ServiceError):
        attachment_service.get_attachment(att.id, owner)


def test_request_out_lists_attachments(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _draft(owner)
    attachment_service.add_attachment(req.id, owner, "q.pdf", "application/pdf", b"x")
    out = request_service.request_out(request_service.get_request(req.id, owner))
    assert out["attachments"][0]["filename"] == "q.pdf"
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Config** — add to `BaseConfig`: `UPLOAD_ROOT = os.environ.get("UPLOAD_ROOT")`; to `TestConfig`: `UPLOAD_ROOT = os.path.join(tempfile.gettempdir(), "capex_test_uploads")` (add `import tempfile` at top of config.py).

- [ ] **Step 4: Storage** — `backend/app/services/storage.py`:
```python
import os

from flask import current_app


class LocalDiskDriver:
    def __init__(self, root):
        self.root = root

    def put(self, rel_path, data):
        full = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)

    def get(self, rel_path):
        with open(os.path.join(self.root, rel_path), "rb") as f:
            return f.read()

    def delete(self, rel_path):
        try:
            os.remove(os.path.join(self.root, rel_path))
        except FileNotFoundError:
            pass


def get_storage():
    root = current_app.config.get("UPLOAD_ROOT") or os.path.join(current_app.instance_path, "uploads")
    return LocalDiskDriver(root)
```

- [ ] **Step 5: request_service** — add a public `can_view`:
```python
def can_view(req, viewer):
    return _can_view(req, viewer)
```
and add to `request_out` (inside the dict):
```python
        "attachments": [
            {"id": a.id, "filename": a.filename, "content_type": a.content_type, "size": a.size}
            for a in req.attachments
        ],
```

- [ ] **Step 6: attachment_service** — `backend/app/services/attachment_service.py`:
```python
import uuid

from app.extensions import db
from app.models import Attachment, CapexRequest
from app.services import request_service
from app.services.errors import ServiceError
from app.services.storage import get_storage

_EDITABLE = ("DRAFT", "REJECTED")


def add_attachment(request_id, uploader, filename, content_type, data):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if req.requestor_id != uploader.id:
        raise ServiceError("Only the requestor can attach files.", 403)
    if req.status not in _EDITABLE:
        raise ServiceError("Attachments can only be changed while the request is editable.")
    rel = f"{request_id}/{uuid.uuid4().hex}_{filename}"
    get_storage().put(rel, data)
    att = Attachment(request_id=request_id, filename=filename, storage_path=rel,
                     content_type=content_type, size=len(data), uploaded_by_id=uploader.id)
    db.session.add(att)
    db.session.commit()
    return att


def get_attachment(att_id, viewer):
    att = db.session.get(Attachment, att_id)
    if att is None:
        raise ServiceError("Attachment not found.", 404)
    if not request_service.can_view(att.request, viewer):
        raise ServiceError("You do not have access to this attachment.", 403)
    return att, get_storage().get(att.storage_path)


def delete_attachment(att_id, viewer):
    att = db.session.get(Attachment, att_id)
    if att is None:
        raise ServiceError("Attachment not found.", 404)
    if att.request.requestor_id != viewer.id:
        raise ServiceError("Only the requestor can delete attachments.", 403)
    if att.request.status not in _EDITABLE:
        raise ServiceError("Attachments can only be changed while the request is editable.")
    get_storage().delete(att.storage_path)
    db.session.delete(att)
    db.session.commit()
```

- [ ] **Step 7: Run → pass.** `pytest tests/test_attachment_service.py -v`

- [ ] **Step 8: Commit** — `git add backend/app/services/storage.py backend/app/services/attachment_service.py backend/app/config.py backend/app/services/request_service.py backend/tests/test_attachment_service.py && git commit -m "feat(backend): attachment storage adapter + service + serialization"`

---

### Task 2: Attachment endpoints

**Files:**
- Modify: `backend/app/blueprints/requests.py`
- Test: `backend/tests/test_attachments_api.py`

- [ ] **Step 1: Failing tests** — `backend/tests/test_attachments_api.py`:
```python
import io
from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _login(client, username="req", roles='["REQUESTOR"]'):
    u = User(username=username, email=f"{username}@x.com", name=username.title(),
             password_hash=hash_password("secret123"), roles=roles)
    db.session.add(u)
    db.session.commit()
    client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    return u


def test_upload_download_delete(client, app):
    _login(client)
    rid = client.post("/api/requests").get_json()["id"]
    up = client.post(f"/api/requests/{rid}/attachments",
                     data={"file": (io.BytesIO(b"quote-bytes"), "quote.pdf")},
                     content_type="multipart/form-data")
    assert up.status_code == 200
    att = up.get_json()["attachments"][0]
    dl = client.get(f"/api/requests/{rid}/attachments/{att['id']}")
    assert dl.status_code == 200 and dl.data == b"quote-bytes"
    d = client.delete(f"/api/requests/{rid}/attachments/{att['id']}")
    assert d.status_code == 200 and d.get_json()["attachments"] == []
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Endpoints** — append to `backend/app/blueprints/requests.py` (add `from flask import Response` and `from app.services import ... attachment_service`):
```python
@bp.post("/<request_id>/attachments")
@login_required
def upload_attachment(request_id):
    f = request.files.get("file")
    if f is None:
        return jsonify(error="No file provided."), 400
    attachment_service.add_attachment(request_id, current_user, f.filename,
                                      f.mimetype or "application/octet-stream", f.read())
    req = request_service.get_request(request_id, current_user)
    return jsonify(request_service.request_out(req))


@bp.get("/<request_id>/attachments/<att_id>")
@login_required
def download_attachment(request_id, att_id):
    att, data = attachment_service.get_attachment(att_id, current_user)
    return Response(data, mimetype=att.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{att.filename}"'})


@bp.delete("/<request_id>/attachments/<att_id>")
@login_required
def delete_attachment_route(request_id, att_id):
    attachment_service.delete_attachment(att_id, current_user)
    req = request_service.get_request(request_id, current_user)
    return jsonify(request_service.request_out(req))
```
(Update the import line to `from app.services import request_service, workflow_service, notify, attachment_service`.)

CSRF note: multipart POST and DELETE are CSRF-protected; the SPA sends `X-CSRFToken`. In tests CSRF is disabled.

- [ ] **Step 4: Run → pass.** `pytest tests/test_attachments_api.py -v`; then `pytest -q`.

- [ ] **Step 5: Commit** — `git add backend/app/blueprints/requests.py backend/tests/test_attachments_api.py && git commit -m "feat(backend): attachment upload/download/delete endpoints"`

---

### Task 3: Attachments UI on the detail page

**Files:**
- Modify: `frontend/src/api/client.ts` (add `apiUpload`)
- Modify: `frontend/src/api/requests.ts` (types + `uploadAttachment`, `deleteAttachment`, `attachmentUrl`)
- Modify: `frontend/src/routes/RequestDetailPage.tsx` (attachments section)

- [ ] **Step 1: apiUpload in client.ts** — append:
```ts
export async function apiUpload<T = unknown>(path: string, formData: FormData): Promise<T> {
  const token = await ensureCsrf()
  const res = await fetch(`/api${path}`, {
    method: 'POST', credentials: 'include', headers: { 'X-CSRFToken': token }, body: formData,
  })
  if (!res.ok) {
    if (res.status === 401) csrfToken = null
    let message = res.statusText
    try { const d = await res.json(); if (d && d.error) message = d.error } catch { /* */ }
    throw new ApiError(res.status, message)
  }
  return (await res.json()) as T
}
```

- [ ] **Step 2: requests.ts** — add to `CapexRequestData`:
```ts
  attachments: { id: string; filename: string; content_type: string; size: number }[]
```
and add:
```ts
import { api, apiUpload } from './client'
// ...
export function uploadAttachment(id: string, file: File): Promise<CapexRequestData> {
  const fd = new FormData()
  fd.append('file', file)
  return apiUpload<CapexRequestData>(`/requests/${id}/attachments`, fd)
}
export function deleteAttachment(id: string, attId: string): Promise<CapexRequestData> {
  return api<CapexRequestData>(`/requests/${id}/attachments/${attId}`, { method: 'DELETE' })
}
export function attachmentUrl(id: string, attId: string): string {
  return `/api/requests/${id}/attachments/${attId}`
}
```
(Change the existing `import { api } from './client'` to `import { api, apiUpload } from './client'`.)

- [ ] **Step 3: Detail page attachments section** — in `RequestDetailPage.tsx`, import `uploadAttachment, deleteAttachment, attachmentUrl`, add a `useRef<HTMLInputElement>` and render before the actions section:
```tsx
      <section>
        <h2 className="mb-1 font-semibold">Attachments</h2>
        <ul className="space-y-1 text-sm">
          {req.attachments.map((a) => (
            <li key={a.id} className="flex items-center gap-3">
              <a className="text-brand-blue hover:underline" href={attachmentUrl(id, a.id)}>{a.filename}</a>
              <span className="text-xs text-slate-500">{(a.size / 1024).toFixed(1)} KB</span>
              {canEdit && (
                <button className="text-xs text-red-600" disabled={busy}
                  onClick={() => act(() => deleteAttachment(id, a.id))}>Remove</button>
              )}
            </li>
          ))}
          {req.attachments.length === 0 && <li className="text-slate-500">No attachments.</li>}
        </ul>
        {canEdit && (
          <div className="mt-2">
            <input type="file" ref={fileRef} className="text-sm" />
            <Button className="ml-2" disabled={busy} onClick={() => {
              const f = fileRef.current?.files?.[0]
              if (f) act(() => uploadAttachment(id, f))
            }}>Upload</Button>
          </div>
        )}
      </section>
```
(Add `const fileRef = useRef<HTMLInputElement>(null)` and `import { useRef } from 'react'` — merge with existing `useState` import.)

- [ ] **Step 4: Build** — `./node_modules/.bin/tsc && ./node_modules/.bin/vite build` → no errors.

- [ ] **Step 5: Commit** — `git add frontend/src && git commit -m "feat(frontend): attachment upload/download/delete on request detail"`

---

## Self-Review
- **Coverage:** storage adapter (disk dev; Blob later), access-checked upload/download/delete (§8), attachments in serialization + detail UI → all tasks. Prod Azure Blob driver deferred (interface ready).
- **Placeholders:** none.
- **Types:** `attachments` added to `CapexRequestData`; `apiUpload` reuses `ensureCsrf`/`csrfToken`/`ApiError` in client.ts; endpoints return `request_out`.
