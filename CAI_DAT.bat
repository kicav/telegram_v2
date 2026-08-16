@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo Telegram Migration Studio V1.1 - Cai dat
echo ============================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows.ps1"
if errorlevel 1 (
  echo.
  echo Cai dat/kiem tra that bai. Xem loi o phia tren.
  pause
  exit /b 1
)
echo.
echo Hoan tat. Ban co the chay CHAY_UNG_DUNG.bat
pause
