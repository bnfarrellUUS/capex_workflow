<#
  CAPEX Flow launcher (PowerShell) — single-server mode.

  The app runs as ONE Flask server on http://localhost:5000: Flask serves the
  built React SPA (frontend/dist) alongside the /api routes. This script:
    * does first-run setup (venv + backend deps + db upgrade + seed, and
      frontend deps);
    * builds the frontend (vite build) so Flask serves the current code;
    * starts Flask via a RELATIVE path from the backend dir, so the '&'/spaces
      in the repo path never reach a parser (that's what broke run-app.bat);
    * opens the browser once the server responds. The server runs in a -NoExit
      window so a startup error stays on screen.

  Usage (from a PowerShell prompt in the repo root):
      .\run-app.ps1
  If you get an execution-policy error, run it once as:
      powershell -ExecutionPolicy Bypass -File .\run-app.ps1
#>

$ErrorActionPreference = 'Stop'
$Root     = $PSScriptRoot
$Backend  = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$VenvPy   = Join-Path $Backend '.venv\Scripts\python.exe'

# --- Backend first-run setup (venv + deps + db + seed) ---
if (-not (Test-Path -LiteralPath $VenvPy)) {
  Write-Host 'Creating Python venv and installing backend deps...' -ForegroundColor Cyan
  python -m venv (Join-Path $Backend '.venv')
  & $VenvPy -m pip install -r (Join-Path $Backend 'requirements.txt')
  Push-Location -LiteralPath $Backend
  try {
    & $VenvPy -m flask db upgrade
    & $VenvPy seed.py
  } finally {
    Pop-Location
  }
}

# --- Frontend first-run setup (deps) ---
if (-not (Test-Path -LiteralPath (Join-Path $Frontend 'node_modules'))) {
  Write-Host 'Installing frontend deps (first run)...' -ForegroundColor Cyan
  Push-Location -LiteralPath $Frontend
  try { npm install } finally { Pop-Location }
}

# --- Build the frontend so Flask serves the current code ---
# Call Vite through node directly (not `npm run build`) so npm's cmd
# script-shell — which the '&' in the path breaks — is never used.
Write-Host 'Building the frontend...' -ForegroundColor Cyan
Push-Location -LiteralPath $Frontend
try { & node '.\node_modules\vite\bin\vite.js' build } finally { Pop-Location }

# --- Launch the single combined server ---
# Path is a single-quoted literal inside the child command, so '&' and spaces
# are treated literally; Flask is started from the backend dir via a relative
# path.
$serverCmd = "Set-Location -LiteralPath '$Backend'; & '.\.venv\Scripts\python.exe' -m flask run"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $serverCmd

# Wait for the server to accept connections, then open the browser.
Write-Host 'Starting the server, opening the website when ready...' -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  try {
    Invoke-WebRequest -Uri 'http://localhost:5000/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null
    $ready = $true
    break
  } catch { Start-Sleep -Seconds 1 }
}
if ($ready) { Start-Process 'http://localhost:5000' }
else { Write-Host 'Server did not respond in time; check the server window for errors.' -ForegroundColor Yellow }

Write-Host ''
Write-Host '================================================================'
Write-Host '  CAPEX Flow: http://localhost:5000   (login: admin / ChangeMe123!)'
Write-Host '================================================================'
Write-Host 'One window opened (the server). Close it to stop the app.'
