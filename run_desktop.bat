@echo off
echo Starting Speech-to-Text Desktop App...
cd /d "%~dp0"
venv\Scripts\python.exe desktop_app.py
pause
