<#
  CAPEX Flow launcher (PowerShell).

  Why this exists: the repo path contains '&' (D&H United Fueling Solutions),
  which breaks run-app.bat — cmd mis-parses the '&' inside the spawned
  `start cmd /k "..."` windows, so they flash and close. This script sidesteps
  that entirely:
    * each server is launched with its working directory set, then invoked via
      a RELATIVE path, so the '&'/space-laden absolute path never reaches a
      parser;
    * the frontend runs Vite through node directly (node node_modules\vite\...)
      instead of `npm run dev`, so npm's cmd script-shell (the thing the '&'
      breaks) is never used and no Git Bash is required;
    * servers open in -NoExit windows, so a startup error stays on screen.

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

# --- Launch both servers in their own windows ---
# Paths are single-quoted string literals inside the child command, so '&' and
# spaces are treated literally (Set-Location -LiteralPath), and each server is
# started from its own directory via a relative path.
$backendCmd  = "Set-Location -LiteralPath '$Backend'; & '.\.venv\Scripts\python.exe' -m flask run"
$frontendCmd = "Set-Location -LiteralPath '$Frontend'; & node '.\node_modules\vite\bin\vite.js'"

Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCmd
Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCmd

Write-Host ''
Write-Host '================================================================'
Write-Host '  Backend:  http://localhost:5000/api/health'
Write-Host '  Frontend: http://localhost:5173   (login: admin / ChangeMe123!)'
Write-Host '================================================================'
Write-Host 'Two windows opened (API + Web). Close them to stop the servers.'
