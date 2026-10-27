@echo off
cd /d "%~dp0"
set "PYTHON=C:\Users\abhis\Documents\Kronos\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo Kronos Python environment was not found.
  echo Expected: %PYTHON%
  pause
  exit /b 1
)
echo Opening Kronos India. Keep this window open while using the app.
"%PYTHON%" launch.py
pause
