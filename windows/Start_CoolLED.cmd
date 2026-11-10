@echo off
setlocal DisableDelayedExpansion
if not defined COOLLED_ROOT (
  if exist "%~dp0.venv\Scripts\pythonw.exe" (
    set "COOLLED_ROOT=%~dp0"
  ) else (
    set "COOLLED_ROOT=%USERPROFILE%\CoolLED"
  )
)
set "LED_PYTHON=%COOLLED_ROOT%\.venv\Scripts\pythonw.exe"
set "LED_CONSOLE=%COOLLED_ROOT%\.venv\Scripts\python.exe"
set "LED_APP=%COOLLED_ROOT%\Player\CoolLED_Uploader.py"
if not exist "%LED_APP%" set "LED_APP=%~dp0CoolLED_Uploader.py"
if not exist "%LED_PYTHON%" (
  echo Python environment not found. Run windows\Install_CoolLED.cmd first.
  pause
  exit /b 1
)
"%LED_CONSOLE%" -c "import tkinter; from PIL import ImageTk"
if errorlevel 1 (
  echo Python's window or image components could not load. Read the error above.
  pause
  exit /b 1
)
if not exist "%LED_APP%" (
  echo Player source not found. Run the installer again.
  pause
  exit /b 1
)
start "" "%LED_PYTHON%" "%LED_APP%"
