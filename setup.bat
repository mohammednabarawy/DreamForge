@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo  DreamForge setup
echo  ================
echo.

if exist "python_embeded\python.exe" (
  echo Found python_embeded\ — refreshing paths and dependencies...
) else if exist "venv\Scripts\python.exe" (
  echo Found venv\ — refreshing dependencies...
) else (
  echo No Python runtime yet. This will install embedded Python on Windows.
)

set "SETUP_PY=scripts\setup_environment.py"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 "%SETUP_PY%" %*
  if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
  goto custom_nodes
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python "%SETUP_PY%" %*
  if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%
  goto custom_nodes
)

echo ERROR: Python 3.10+ is required to run setup.
echo Install from https://www.python.org/downloads/ then run setup.bat again.
exit /b 1

:custom_nodes
echo Checking ComfyUI custom nodes...
if not exist "backend\repositories\ComfyUI\custom_nodes\comfyui_controlnet_aux" (
  echo Cloning comfyui_controlnet_aux...
  git clone https://github.com/Fannovel16/comfyui_controlnet_aux "backend\repositories\ComfyUI\custom_nodes\comfyui_controlnet_aux"
)
if not exist "backend\repositories\ComfyUI\custom_nodes\ComfyUI-GGUF" (
  echo Cloning ComfyUI-GGUF...
  git clone https://github.com/city96/ComfyUI-GGUF "backend\repositories\ComfyUI\custom_nodes\ComfyUI-GGUF"
)
exit /b 0
