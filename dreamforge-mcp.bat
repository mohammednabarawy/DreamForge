@echo off
call "%~dp0scripts\dreamforge_env.bat" || exit /b 1
"%DREAMFORGE_PYTHON%" %DREAMFORGE_PYTHON_FLAGS% "%DREAMFORGE_ROOT%\dreamforge_mcp_server.py" %*
