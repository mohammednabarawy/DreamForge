@echo off
setlocal
for %%I in ("%~dp0.") do set "DREAMFORGE_PORTABLE_ROOT=%%~fI"
set "DREAMFORGE_ROOT=%DREAMFORGE_PORTABLE_ROOT%\backend"
set "DREAMFORGE_BACKEND_ROOT=%DREAMFORGE_PORTABLE_ROOT%\backend"
set "DREAMFORGE_INSTALL_ROOT=%DREAMFORGE_PORTABLE_ROOT%"
set "DREAMFORGE_DATA_ROOT=%DREAMFORGE_PORTABLE_ROOT%"
set "DREAMFORGE_PACKAGED=1"
set "DREAMFORGE_MODELS_ROOT="

set "APP=%DREAMFORGE_PORTABLE_ROOT%\apps\desktop\src-tauri\target\release\dreamforge.exe"
if not exist "%APP%" (
  echo DreamForge portable release is not built yet.
  echo Build it from apps\desktop with: npm run tauri build -- --no-bundle
  pause
  exit /b 1
)

"%APP%"
