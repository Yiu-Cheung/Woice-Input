@echo off
cd /d "%~dp0"
echo Starting app with debug output...
venv\Scripts\python.exe desktop_app.py
pause
