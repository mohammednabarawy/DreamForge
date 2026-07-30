@echo off
setlocal
set "VSDEVCMD="

for %%V in (
  "%ProgramFiles(x86)%\Microsoft Visual Studio\18\BuildTools\Common7\Tools\VsDevCmd.bat"
  "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
  "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat"
  "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat"
  "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat"
  "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\BuildTools\Common7\Tools\VsDevCmd.bat"
) do (
  if not defined VSDEVCMD if exist %%~V set "VSDEVCMD=%%~V"
)

if defined VSDEVCMD (
  call "%VSDEVCMD%" -no_logo -arch=amd64
  exit /b 0
)

for /f "delims=" %%R in ('where rc.exe 2^>nul') do exit /b 0

for /d %%K in ("%ProgramFiles(x86)%\Windows Kits\10\bin\10.0.*") do (
  if exist "%%K\x64\rc.exe" (
    set "PATH=%%K\x64;%PATH%"
    exit /b 0
  )
)

echo.
echo  Windows SDK resource compiler ^(rc.exe^) not found.
echo  Install Visual Studio Build Tools with the Windows 10/11 SDK, or run:
echo    winget install Microsoft.WindowsSDK.10.0.22621
echo.
exit /b 1
