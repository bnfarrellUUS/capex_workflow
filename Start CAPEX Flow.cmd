@echo off
rem Double-click this to start CAPEX Flow. It runs run-app.ps1 with the
rem execution-policy bypass built in, so no PowerShell setup is needed.
rem The '&' in the repo path is safe here: %~dp0 is passed quoted to -File.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-app.ps1"
if errorlevel 1 (
  echo.
  echo Something went wrong starting the app. See the messages above.
  pause
)
