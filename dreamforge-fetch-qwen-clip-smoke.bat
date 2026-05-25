@echo off
call "%~dp0scripts\dreamforge_env.bat" || exit /b 1
cd /d "%~dp0"
"%DREAMFORGE_PYTHON%" %DREAMFORGE_PYTHON_FLAGS% "%DREAMFORGE_ROOT%\fetch_qwen_clip_smoke.py" %*
