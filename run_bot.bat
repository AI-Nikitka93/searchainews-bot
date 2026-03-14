@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv" (
  call "install.bat"
)

call ".venv\Scripts\activate.bat"
python "validator.py"
if errorlevel 1 exit /b 1
python -m bot.main

endlocal
