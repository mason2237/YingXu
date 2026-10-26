@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-web\Scripts\pythonw.exe" (
  echo Python environment missing. See README.md.
  pause
  exit /b 2
)
if not exist "work\tools\electron-45.0.0\electron.exe" (
  echo Electron runtime missing. Run .venv-web\Scripts\python.exe scripts/setup_electron.py
  pause
  exit /b 2
)
start "YingXu Electron" ".venv-web\Scripts\pythonw.exe" "%~dp0run_electron.py" %*
