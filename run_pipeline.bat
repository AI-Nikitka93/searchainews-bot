@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv" (
  call "install.bat"
)

call ".venv\Scripts\activate.bat"
python "scraper.py"
python "ai_analyzer.py"
python "scripts\push_to_worker.py"

endlocal
