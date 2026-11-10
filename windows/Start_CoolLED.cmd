@echo off
setlocal
set "LED_PYTHON=%USERPROFILE%\CoolLED\coolledx-driver-main\.venv\Scripts\pythonw.exe"
set "LED_CONSOLE=%USERPROFILE%\CoolLED\coolledx-driver-main\.venv\Scripts\python.exe"
if not exist "%LED_PYTHON%" (
  echo The Python environment from the panel setup was not found:
  echo %LED_PYTHON%
  echo Keep the existing CoolLED folders in your user profile.
  pause
  exit /b 1
)
"%LED_CONSOLE%" -c "import tkinter; from PIL import ImageTk" >nul 2>&1
if errorlevel 1 (
  echo The uploader could not load Python's window or image components.
  echo Run this check and share the error:
  echo "%LED_CONSOLE%" -c "import tkinter; from PIL import ImageTk"
  "%LED_CONSOLE%" -c "import tkinter; from PIL import ImageTk"
  pause
  exit /b 1
)
start "" "%LED_PYTHON%" "%~dp0CoolLED_Uploader.py"
