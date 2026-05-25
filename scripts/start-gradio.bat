@echo off
call "%~dp0dreamforge_env.bat" || exit /b 1
cd /d "%~dp0..\backend"
"%DREAMFORGE_PYTHON%" %DREAMFORGE_PYTHON_FLAGS% entry_with_update.py %*
