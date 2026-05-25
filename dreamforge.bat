@echo off
setlocal
cd /d "%~dp0"
call "%~dp0scripts\dreamforge_env.bat" || exit /b 1
if exist "%USERPROFILE%\.cargo\bin\cargo.exe" (
  set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
) else (
  echo ERROR: cargo not found. Install Rust from https://rustup.rs/
  exit /b 1
)
set "NEED_DESKTOP_NPM=0"
if not exist "apps\desktop\node_modules" set "NEED_DESKTOP_NPM=1"
if not exist "apps\desktop\node_modules\.bin\tsc.cmd" set "NEED_DESKTOP_NPM=1"
if not exist "apps\desktop\node_modules\typescript\bin\tsc" set "NEED_DESKTOP_NPM=1"
if "%NEED_DESKTOP_NPM%"=="1" (
  echo Installing DreamForge desktop dependencies...
  pushd apps\desktop
  call npm install
  if errorlevel 1 exit /b 1
  popd
)
set DREAMFORGE_ROOT=%CD%\backend
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":1420" ^| findstr "LISTENING"') do (
  echo Stopping stale process on port 1420 ^(PID %%a^)...
  taskkill /PID %%a /F >nul 2>&1
)
taskkill /IM dreamforge.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul
pushd apps\desktop
call npm run tauri dev
popd
