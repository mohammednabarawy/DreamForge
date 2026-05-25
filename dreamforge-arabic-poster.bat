@echo off
call "%~dp0scripts\dreamforge_env.bat" || exit /b 1
cd /d "%~dp0"
"%DREAMFORGE_PYTHON%" %DREAMFORGE_PYTHON_FLAGS% "%DREAMFORGE_ROOT%\arabic_poster_pipeline.py" %*
