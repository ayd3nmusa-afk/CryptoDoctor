@echo off
REM IST-20 Desktop - double-click to open the live dashboard.
cd /d "%~dp0"
set PY=python
python --version >nul 2>&1 || set PY=py -3
%PY% --version >nul 2>&1 || (echo Install Python 3.10+ from python.org first. & pause & exit /b 1)
%PY% -c "import requests, matplotlib" >nul 2>&1 || %PY% -m pip install -q -r requirements.txt
%PY% app.py
if errorlevel 1 pause
