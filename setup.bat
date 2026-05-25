@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo  DreamForge setup
echo  ================
echo.

if exist "python_embeded\python.exe" (
  echo Found python_embeded\ — refreshing paths and dependencies...
) else if exist "venv\Scripts\python.exe" (
  echo Found venv\ — refreshing dependencies...
) else (
  echo No Python runtime yet. This will install embedded Python on Windows.
)

set "SETUP_PY=scripts\setup_environment.py"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 "%SETUP_PY%" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python "%SETUP_PY%" %*
  exit /b %ERRORLEVEL%
)

echo ERROR: Python 3.10+ is required to run setup.
echo Install from https://www.python.org/downloads/ then run setup.bat again.
exit /b 1
