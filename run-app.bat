@echo off
setlocal enableextensions
title CAPEX Tracking (Flask API + React)

rem The repo path contains '&', which breaks npm's default cmd script-shell.
rem Point npm's script-shell at Git Bash so "npm run dev" works.
set "GITBASH=%ProgramFiles%\Git\bin\bash.exe"
if not exist "%GITBASH%" set "GITBASH=%LocalAppData%\Programs\Git\bin\bash.exe"
if exist "%GITBASH%" set "npm_config_script_shell=%GITBASH%"

rem --- Backend first-run setup + launch ---
if not exist "%~dp0backend\.venv\" (
  echo Creating Python venv and installing backend deps...
  pushd "%~dp0backend" && python -m venv .venv && call .venv\Scripts\activate && pip install -r requirements.txt && flask db upgrade && python seed.py && popd
)
start "CAPEX API" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate && flask run"

rem --- Frontend first-run setup + launch ---
if not exist "%~dp0frontend\node_modules\" (
  echo Installing frontend deps ^(first run^)...
  pushd "%~dp0frontend" && call npm install && popd
)
start "CAPEX Web" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ================================================================
echo   Backend:  http://localhost:5000/api/health
echo   Frontend: http://localhost:5173   (login: admin / ChangeMe123!)
echo ================================================================
