@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua co moi truong Python cua ung dung.
  echo Hay chay CAI_DAT.bat truoc.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_windows.ps1"
if errorlevel 1 (
  echo.
  echo Build that bai. Xem loi o phia tren.
  pause
  exit /b 1
)
echo.
echo Build hoan tat. Xem thu muc dist.
pause
