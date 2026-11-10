@echo off
setlocal DisableDelayedExpansion
py -3.13 "%~dp0..\setup_player.py" %*
if errorlevel 1 (
  echo.
  echo Installation did not complete. Read the error above before retrying.
  pause
  exit /b 1
)
pause
