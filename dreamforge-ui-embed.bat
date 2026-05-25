@echo off
call "%~dp0scripts\dreamforge_env.bat" || exit /b 1
echo Starting classic DreamForge Gradio UI on http://127.0.0.1:7860 ...
start "DreamForge Gradio" cmd /k "%~dp0scripts\start-gradio.bat"
