---
name: verify
description: Build, launch, and drive CAPEX Flow locally to verify changes end-to-end
---

# Verifying CAPEX Flow changes

Single-server app: Flask serves the built SPA + `/api` on port 5000.

## Build & launch

```powershell
# 1. Rebuild the SPA if frontend changed (no dev server; Flask serves dist/).
#    Call binaries via node — the & in the repo path breaks npm's script shell.
cd frontend; node ./node_modules/vite/bin/vite.js build

# 2. Start the server (background). EMAIL_ENABLED=0 stops Outlook sends.
cd ..\backend; $env:EMAIL_ENABLED='0'; .\.venv\Scripts\python.exe -m flask run --port 5000
```

Health check: `GET http://localhost:5000/api/health` → `{"status":"ok"}`.

## Drive

- Use the Playwright MCP browser tools against `http://localhost:5000`.
- Dev login: **admin / ChangeMe123!** (seeded by `python seed.py`).
- Request IDs are UUID hex, not integers — fetch a real one first:
  `fetch('/api/requests')` from `browser_evaluate` (items have `id`, `number`).
- Cookie surgery (e.g. simulating a browser restart by dropping the HttpOnly
  `session` cookie) needs `browser_run_code_unsafe` with `page.context()`;
  `document.cookie` can't see HttpOnly cookies.

## Gotchas

- The dev DB (`backend/instance/capex_dev.db`) persists between runs; seeded
  requests may all be DRAFT — create/submit one via the UI if you need a
  PENDING_* state.
- RequestDetailPage shows "Loading…" forever on a 404 id (known behavior).
