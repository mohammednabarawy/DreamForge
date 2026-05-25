@echo off
echo Stopping DreamForge dev processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":1420" ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>&1
taskkill /IM dreamforge.exe /F >nul 2>&1
echo Done.
