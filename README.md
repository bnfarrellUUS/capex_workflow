# CAPEX Tracking — United Uptime Services

Internal web app to submit, route, approve, and search capital-expenditure requests.

## Stack
- **backend/** — Flask API (Python), SQLAlchemy, SQLite (dev) / Azure SQL Server (prod).
  Also serves the built React SPA, so the whole app runs as one server.
- **frontend/** — React + Vite + TypeScript SPA (Tailwind, brand colors), built to
  `frontend/dist` and served by Flask.

## Run (Windows)
Double-click **`Start CAPEX Flow.cmd`**, or run **`.\run-app.ps1`** from a
PowerShell prompt (use `powershell -ExecutionPolicy Bypass -File .\run-app.ps1`
if execution is blocked). It builds the frontend and starts one server, then
opens the browser. Manually:

    # build the frontend (served by Flask)
    cd frontend && npm install && node ./node_modules/vite/bin/vite.js build
    # backend serves the SPA + API on one port
    cd ../backend && python -m venv .venv && source .venv/Scripts/activate
    pip install -r requirements.txt && flask db upgrade && python seed.py && flask run

App: http://localhost:5000 · Login: admin@uniteduptime.com / ChangeMe123!

## Test
    cd backend && pytest -q
    cd frontend && npm test && npm run build

Design docs & milestone plans live in `docs/superpowers/`.
