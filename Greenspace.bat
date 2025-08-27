@echo off
REM Greenspace Standalone App Launcher for Windows
REM Double-click this file to run the Greenspace app

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python 3 is required but not installed.
    echo Please install Python 3 from python.org and try again.
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "local_venv" (
    echo Setting up Greenspace for first run...
    python -m venv local_venv
    call local_venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install -r local_app\requirements.txt
    echo Setup complete!
) else (
    call local_venv\Scripts\activate.bat
)

REM Start the server
echo Starting Greenspace app...
start /b python local_app\main.py

REM Wait a moment for server to start
timeout /t 2 /nobreak >nul

REM Open in default browser
start http://127.0.0.1:8000

echo.
echo Greenspace is running at: http://127.0.0.1:8000
echo Press any key to stop the server...
pause >nul

REM Kill the Python process
taskkill /f /im python.exe >nul 2>&1