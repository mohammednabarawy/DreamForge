@echo off
call "%~dp0scripts\dreamforge_env.bat" || exit /b 1
cd /d "%~dp0"
pushd backend
"%DREAMFORGE_PYTHON%" %DREAMFORGE_PYTHON_FLAGS% entry_with_update.py --preset anime %*
popd
pause
