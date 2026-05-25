@echo off
for %%I in ("%~dp0..") do set "DREAMFORGE_REPO=%%~fI"
set "DREAMFORGE_ROOT=%DREAMFORGE_REPO%\backend"
set "DREAMFORGE_PYTHON="
set "DREAMFORGE_PYTHON_FLAGS=-s"

if exist "%DREAMFORGE_REPO%\python_embeded\python.exe" (
  set "DREAMFORGE_PYTHON=%DREAMFORGE_REPO%\python_embeded\python.exe"
  goto :env_ok
)

if exist "%DREAMFORGE_REPO%\venv\Scripts\python.exe" (
  set "DREAMFORGE_PYTHON=%DREAMFORGE_REPO%\venv\Scripts\python.exe"
  set "DREAMFORGE_PYTHON_FLAGS="
  goto :env_ok
)

echo.
echo  DreamForge Python runtime not found.
echo  Run setup once from the repo root:
echo    setup.bat
echo.
exit /b 1

:env_ok
exit /b 0
