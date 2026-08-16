@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua co moi truong Python cua ung dung.
  echo Hay chay CAI_DAT.bat truoc.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m tms
if errorlevel 1 pause
