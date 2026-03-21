@echo off
:: =============================================================================
:: Echo Solutions — Windows Launcher
:: =============================================================================
::
:: Responsibilities
::   1. Validate host prerequisites (Python 3.8+).
::   2. Delegate dependency bootstrap to setup_installer.py.
::   3. Activate the project virtual environment.
::   4. Validate the .env file is present.
::   5. Create required runtime directories (logs\, media\, staticfiles\).
::   6. Apply Django database migrations.
::   7. Start the development server.
::
:: Usage
::   run.bat                        Normal start (port 8000)
::   run.bat --port 9000            Override port
::   run.bat --host 0.0.0.0         Bind to all interfaces
::   run.bat --repair               Force-reinstall dependencies first
::   run.bat --no-migrate           Skip migrations
::   run.bat --settings production  Use a specific settings module
::   run.bat --help                 Show this help
::
:: Exit codes
::   0  Success
::   1  Fatal error
::   2  Prerequisite check failed
::   3  Installer failed
::   4  Migration failed
:: =============================================================================

setlocal EnableDelayedExpansion
setlocal EnableExtensions

:: ---------------------------------------------------------------------------
:: Defaults
:: ---------------------------------------------------------------------------
set "ARG_PORT=8000"
set "ARG_HOST=127.0.0.1"
set "ARG_SETTINGS=Echo_Solutions.settings.development"
set "ARG_REPAIR=0"
set "ARG_NO_MIGRATE=0"
set "SCRIPT_DIR=%~dp0"
:: Remove trailing backslash
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: ---------------------------------------------------------------------------
:: Parse arguments
:: ---------------------------------------------------------------------------
:parse_args
if "%~1"=="" goto :end_args
if /i "%~1"=="--help"       goto :show_help
if /i "%~1"=="--repair"     ( set "ARG_REPAIR=1"           & shift & goto :parse_args )
if /i "%~1"=="--no-migrate" ( set "ARG_NO_MIGRATE=1"       & shift & goto :parse_args )
if /i "%~1"=="--port" (
    if "%~2"=="" ( call :die "--port requires a value." )
    set "ARG_PORT=%~2" & shift & shift & goto :parse_args
)
if /i "%~1"=="--host" (
    if "%~2"=="" ( call :die "--host requires a value." )
    set "ARG_HOST=%~2" & shift & shift & goto :parse_args
)
if /i "%~1"=="--settings" (
    if "%~2"=="" ( call :die "--settings requires a value." )
    set "ARG_SETTINGS=%~2" & shift & shift & goto :parse_args
)
call :die "Unknown argument: %~1  (use --help for usage)"
:end_args

:: ---------------------------------------------------------------------------
:: Banner
:: ---------------------------------------------------------------------------
echo.
echo  ^+----------------------------------------------------------^+
echo  ^|       Echo Solutions  --  Application Launcher          ^|
echo  ^|           Property Management Platform                  ^|
echo  ^+----------------------------------------------------------^+
echo.

:: ---------------------------------------------------------------------------
:: Step 1 — Python detection
:: ---------------------------------------------------------------------------
call :section "Python"
where python >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    call :die "Python not found on PATH.^
Please install Python 3.8+ from https://python.org^
and ensure it is added to the system PATH."
)

:: Verify minimum version
python -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    call :die "Python 3.8+ required. Found: !PY_VER!"
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
call :info "!PY_VER! detected  [OK]"

:: ---------------------------------------------------------------------------
:: Step 2 — Dependency installer
:: ---------------------------------------------------------------------------
call :section "Dependencies"
if not exist "%SCRIPT_DIR%\setup_installer.py" (
    call :die "setup_installer.py not found at %SCRIPT_DIR%\setup_installer.py"
)

call :info "Running dependency installer ..."
set "INSTALLER_ARGS="
if "!ARG_REPAIR!"=="1" set "INSTALLER_ARGS=--repair"

python "%SCRIPT_DIR%\setup_installer.py" !INSTALLER_ARGS!
if !ERRORLEVEL! NEQ 0 (
    call :die "Dependency installation failed.^
Review %SCRIPT_DIR%\installer.log for details.^
Try running:  python setup_installer.py --repair"
)

:: ---------------------------------------------------------------------------
:: Step 3 — Virtual environment activation
:: ---------------------------------------------------------------------------
call :section "Virtual Environment"
if exist "%SCRIPT_DIR%\.venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\.venv\Scripts\activate.bat"
    if !ERRORLEVEL! NEQ 0 (
        call :warn "Virtual environment activation returned non-zero. Continuing with system Python."
    ) else (
        call :info "Virtual environment activated: %SCRIPT_DIR%\.venv"
        for /f "tokens=*" %%v in ('python --version 2^>^&1') do (
            call :detail "Python: %%v"
        )
    )
) else (
    call :warn "Virtual environment not found at %SCRIPT_DIR%\.venv"
    call :warn "Using system Python. This is not recommended for production."
)

:: ---------------------------------------------------------------------------
:: Step 4 — Environment file check
:: ---------------------------------------------------------------------------
call :section "Environment Configuration"
if not exist "%SCRIPT_DIR%\.env" (
    call :warn ".env file not found at %SCRIPT_DIR%\.env"
    call :warn "The application requires environment variables for:"
    call :detail "  SECRET_KEY, database credentials, API keys (Stripe, M-Pesa, etc.)"
    call :warn "Copy .env.example to .env and fill in your values."

    :: Block startup if production settings are selected
    echo !ARG_SETTINGS! | findstr /i "production" >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        call :die ".env is mandatory when using the production settings module."
    )
) else (
    call :info ".env file found  [OK]"
)

set "DJANGO_SETTINGS_MODULE=!ARG_SETTINGS!"
call :info "Django settings : !DJANGO_SETTINGS_MODULE!"

:: ---------------------------------------------------------------------------
:: Step 5 — Runtime directories
:: ---------------------------------------------------------------------------
call :section "Runtime Directories"
set "_CREATED=0"

if not exist "%SCRIPT_DIR%\logs" (
    mkdir "%SCRIPT_DIR%\logs" 2>nul
    if !ERRORLEVEL! NEQ 0 ( call :warn "Could not create logs\ directory." ) else (
        call :info "Created: %SCRIPT_DIR%\logs"
        set "_CREATED=1"
    )
)
if not exist "%SCRIPT_DIR%\media" (
    mkdir "%SCRIPT_DIR%\media" 2>nul
    if !ERRORLEVEL! NEQ 0 ( call :warn "Could not create media\ directory." ) else (
        call :info "Created: %SCRIPT_DIR%\media"
        set "_CREATED=1"
    )
)
if not exist "%SCRIPT_DIR%\staticfiles" (
    mkdir "%SCRIPT_DIR%\staticfiles" 2>nul
    if !ERRORLEVEL! NEQ 0 ( call :warn "Could not create staticfiles\ directory." ) else (
        call :info "Created: %SCRIPT_DIR%\staticfiles"
        set "_CREATED=1"
    )
)
if "!_CREATED!"=="0" (
    call :info "All runtime directories present  [OK]"
)

:: ---------------------------------------------------------------------------
:: Step 6 — Database migrations
:: ---------------------------------------------------------------------------
if "!ARG_NO_MIGRATE!"=="1" (
    call :warn "Skipping migrations (--no-migrate was set)."
    goto :skip_migrate
)

call :section "Database Migrations"
call :info "Applying migrations ..."

python manage.py migrate --run-syncdb
if !ERRORLEVEL! NEQ 0 (
    call :die "Database migrations failed.^
Common causes:^
  - DATABASE_URL / DB_* variables not set in .env^
  - Database server not running^
  - Migration conflict: python manage.py migrate --fake-initial"
)
call :info "Migrations applied  [OK]"

:skip_migrate

:: ---------------------------------------------------------------------------
:: Step 7 — Server startup
:: ---------------------------------------------------------------------------
call :section "Development Server"

:: Validate port is a number in valid range
set /a "_PORT_CHECK=!ARG_PORT!" 2>nul
if "!_PORT_CHECK!"=="" (
    call :die "Invalid port: !ARG_PORT!  (must be a number between 1 and 65535)"
)
if !_PORT_CHECK! LSS 1 (
    call :die "Invalid port: !ARG_PORT!  (must be >= 1)"
)
if !_PORT_CHECK! GTR 65535 (
    call :die "Invalid port: !ARG_PORT!  (must be <= 65535)"
)

if "!ARG_HOST!"=="0.0.0.0" (
    call :warn "Binding to 0.0.0.0 -- server is accessible from the network."
    call :warn "Do not use this without a reverse proxy in production."
)

call :info "Starting Django development server ..."
call :info "  Address  :  http://!ARG_HOST!:!ARG_PORT!/"
call :info "  Settings :  !DJANGO_SETTINGS_MODULE!"
call :info "  Press Ctrl-C to stop."
echo.

python manage.py runserver "!ARG_HOST!:!ARG_PORT!"
if !ERRORLEVEL! NEQ 0 (
    echo.
    call :error "Django server exited with an error."
    call :detail "Check %SCRIPT_DIR%\logs\Echo_Solutions.log for application details."
    pause
    exit /b 1
)

endlocal
exit /b 0

:: =============================================================================
:: Subroutines
:: =============================================================================

:section
echo.
echo [---- %~1 ----]
goto :eof

:info
echo [INFO]   %~1
goto :eof

:warn
echo [WARN]   %~1
goto :eof

:error
echo [ERROR]  %~1 1>&2
goto :eof

:detail
echo          %~1
goto :eof

:die
echo.
echo [ERROR]  %~1 1>&2
echo.
echo Aborting. 1>&2
pause
exit /b 1

:show_help
echo.
echo Usage:
echo   run.bat                        Normal start (port 8000)
echo   run.bat --port 9000            Override port
echo   run.bat --host 0.0.0.0         Bind to all interfaces
echo   run.bat --repair               Force-reinstall dependencies
echo   run.bat --no-migrate           Skip migrations
echo   run.bat --settings production  Use production settings module
echo   run.bat --help                 Show this help
echo.
exit /b 0