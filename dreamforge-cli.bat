@echo off
call "%~dp0scripts\dreamforge_env.bat" || exit /b 1
cd /d "%~dp0"
"%DREAMFORGE_PYTHON%" %DREAMFORGE_PYTHON_FLAGS% "%DREAMFORGE_ROOT%\dreamforge_cli_direct.py" %*
