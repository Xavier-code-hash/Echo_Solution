@echo off
:: ============================================================
:: run.bat — Windows launcher
:: Runs setup_installer.py then starts the Django application.
:: ============================================================
setlocal EnableDelayedExpansion

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║        Dependency Installer (Windows)    ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ── 1. Ensure Python is available ───────────────────────────
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Please install Python 3.8+ and add it to PATH.
    pause
    exit /b 1
)

:: ── 2. Run the installer ─────────────────────────────────────
echo [INFO] Running dependency installer...
python setup_installer.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Installer failed. Check installer.log for details.
    pause
    exit /b 1
)

:: ── 3. Activate virtual environment ──────────────────────────
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [INFO] Virtual environment activated.
) else (
    echo [WARN] Virtual environment not found — using system Python.
)

:: ── 4. Start the Django app ───────────────────────────────────
echo [INFO] Starting Django development server...
python manage.py migrate --run-syncdb
python manage.py runserver

pause
