# CAPEX Tracking — United Uptime Services

Internal web app to submit, route, approve, and search capital-expenditure requests.

## Stack
- **backend/** — Flask API (Python), SQLAlchemy, SQLite (dev) / Azure SQL Server (prod)
- **frontend/** — React + Vite + TypeScript SPA (Tailwind, brand colors)

## Run (Windows, Git Bash — the repo path contains `&`)
Run **`.\run-app.ps1`** from a PowerShell prompt (use
`powershell -ExecutionPolicy Bypass -File .\run-app.ps1` if execution is
blocked), or manually:

    # backend
    cd backend && python -m venv .venv && source .venv/Scripts/activate
    pip install -r requirements.txt && flask db upgrade && python seed.py && flask run
    # frontend (separate shell)
    cd frontend && npm install && npm run dev

Backend: http://localhost:5000 · Frontend: http://localhost:5173 · Login: admin / ChangeMe123!

## Test
    cd backend && pytest -q
    cd frontend && npm test && npm run build

Design docs & milestone plans live in `docs/superpowers/`.
