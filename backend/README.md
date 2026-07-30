# CAPEX Backend (Flask)

## Setup (Git Bash — the repo path contains `&`, so use Git Bash, not cmd/PowerShell)

    cd backend
    python -m venv .venv
    source .venv/Scripts/activate
    pip install -r requirements.txt
    flask db upgrade
    python seed.py

## Run

    flask run --port 5100   # http://localhost:5100  (GET /api/health -> {"status":"ok"})

## Test

    pytest -v

Dev login (after seed): admin / ChangeMe123!
