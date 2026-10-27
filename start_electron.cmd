@echo off
setlocal
cd /d "%~dp0"
set "YINGXU_LAUNCHER=.venv-core\Scripts\pythonw.exe"
if not exist "%YINGXU_LAUNCHER%" set "YINGXU_LAUNCHER=.venv-build\Scripts\pythonw.exe"
if not exist "%YINGXU_LAUNCHER%" (
  echo Python environment missing. See README.md.
  pause
  exit /b 2
)
if not exist "work\tools\electron-45.0.0\electron.exe" (
  echo Electron runtime missing. See docs/DEVELOPMENT.md for setup_electron.py.
  pause
  exit /b 2
)
start "YingXu Electron" "%YINGXU_LAUNCHER%" "%~dp0run_electron.py" %*
