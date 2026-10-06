@echo off
REM IST-20 launcher — double-click to refresh. Installs deps on first run.
cd /d "%~dp0"
python --version >nul 2>&1 || (echo Install Python 3.10+ from python.org first. & pause & exit /b 1)
pip install -q -r requirements.txt
python run.py %*
echo.
echo Opening reports folder...
start "" "%~dp0reports"
pause
