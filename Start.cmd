@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Python environment is missing. See README.md.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0app.py"
