@echo off
setlocal
cd /d "%~dp0"
python scripts\sync_assets.py %*
if errorlevel 1 (
  echo.
  echo [failed] sync_assets.py exited with error.
  pause
  exit /b 1
)
echo.
pause
