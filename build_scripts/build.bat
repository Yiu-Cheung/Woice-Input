@echo off
echo === SpeechToText Build ===

:: Run from project root
cd /d "%~dp0\.."

:: Kill running instance if any
tasklist /FI "IMAGENAME eq SpeechToText.exe" 2>NUL | find /I "SpeechToText.exe" >NUL
if %ERRORLEVEL%==0 (
    echo Stopping running SpeechToText.exe...
    taskkill /F /IM SpeechToText.exe >NUL 2>&1
    timeout /t 2 /nobreak >NUL
)

:: Build
echo Building...
venv\Scripts\pyinstaller.exe build_scripts\desktop_app.spec --clean --noconfirm --distpath dist --workpath build
if %ERRORLEVEL% NEQ 0 (
    echo BUILD FAILED
    pause
    exit /b 1
)

echo.
echo === Build complete: dist\SpeechToText.exe ===
pause
