@echo off
REM One-time setup for Windows. Requires Python 3.11+ on PATH.
cd /d "%~dp0"
python --version >nul 2>&1 || (echo Python is not installed or not on PATH. Install Python 3.11+ from python.org & pause & exit /b 1)
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || (echo Library installation failed & pause & exit /b 1)
if exist instance\fdpa.sqlite3 (
  echo A database already exists - leaving it untouched.
) else (
  echo Building the DEMO database with fictional data...
  python manage.py demo
)
echo.
echo Setup complete. Start the system with run.bat
pause
