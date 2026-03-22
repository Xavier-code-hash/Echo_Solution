#!/usr/bin/env bash
# =============================================================================
# Echo Solutions — Unix / macOS Launcher
# =============================================================================
#
# Responsibilities
# ----------------
#   1. Validate host prerequisites (Python 3.8+, pip).
#   2. Delegate dependency bootstrap to setup_installer.py.
#   3. Activate the project virtual environment.
#   4. Validate the .env file is present.
#   5. Create required runtime directories (logs/, media/, staticfiles/).
#   6. Apply Django database migrations.
#   7. Start the development server (or run a custom management command).
#
# Usage
# -----
#   ./run.sh                        # Normal start
#   ./run.sh --port 9000            # Override server port (default: 8000)
#   ./run.sh --host 0.0.0.0         # Bind to all interfaces
#   ./run.sh --no-migrate           # Skip migrations (useful in production)
#   ./run.sh --repair               # Force-reinstall dependencies before start
#   ./run.sh --settings production  # Use a specific Django settings module
#   ./run.sh -- createsuperuser     # Pass any manage.py command after --
#
# Exit codes mirror setup_installer.py.
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_NAME="Echo Solutions"
readonly MIN_PYTHON_MAJOR=3
readonly MIN_PYTHON_MINOR=8
readonly DEFAULT_PORT=8000
readonly DEFAULT_HOST="127.0.0.1"
readonly DEFAULT_SETTINGS="Echo_Solutions.settings.development"
readonly VENV_DIR="${SCRIPT_DIR}/.venv"
readonly VENV_ACTIVATE="${VENV_DIR}/bin/activate"
readonly ENV_FILE="${SCRIPT_DIR}/.env"
readonly LOG_DIR="${SCRIPT_DIR}/logs"
readonly MEDIA_DIR="${SCRIPT_DIR}/media"
readonly STATIC_DIR="${SCRIPT_DIR}/staticfiles"

# ---------------------------------------------------------------------------
# ANSI colour helpers (suppressed when not writing to a terminal)
# ---------------------------------------------------------------------------

if [[ -t 1 ]]; then
    C_RESET="\033[0m"
    C_BOLD="\033[1m"
    C_GREEN="\033[0;32m"
    C_YELLOW="\033[1;33m"
    C_RED="\033[0;31m"
    C_CYAN="\033[0;36m"
    C_DIM="\033[2m"
else
    C_RESET="" C_BOLD="" C_GREEN="" C_YELLOW="" C_RED="" C_CYAN="" C_DIM=""
fi

info()    { echo -e "${C_GREEN}[INFO]${C_RESET}   $*"; }
warn()    { echo -e "${C_YELLOW}[WARN]${C_RESET}   $*"; }
error()   { echo -e "${C_RED}[ERROR]${C_RESET}  $*" >&2; }
detail()  { echo -e "${C_DIM}         $*${C_RESET}"; }
section() { echo -e "\n${C_BOLD}${C_CYAN}── $* ${C_RESET}"; }
die()     {
    error "$*"
    echo -e "${C_RED}Aborting.${C_RESET}" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

print_banner() {
    echo -e "${C_CYAN}"
    echo "  ╔══════════════════════════════════════════════════════╗"
    echo "  ║          Echo Solutions — Application Launcher       ║"
    echo "  ║              Property Management Platform            ║"
    echo "  ╚══════════════════════════════════════════════════════╝"
    echo -e "${C_RESET}"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

ARG_PORT="${DEFAULT_PORT}"
ARG_HOST="${DEFAULT_HOST}"
ARG_SETTINGS="${DEFAULT_SETTINGS}"
ARG_REPAIR=false
ARG_NO_MIGRATE=false
ARG_MANAGE_CMD=""

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --port)
                [[ -z "${2-}" ]] && die "--port requires a value."
                ARG_PORT="$2"; shift 2 ;;
            --host)
                [[ -z "${2-}" ]] && die "--host requires a value."
                ARG_HOST="$2"; shift 2 ;;
            --settings)
                [[ -z "${2-}" ]] && die "--settings requires a value."
                ARG_SETTINGS="$2"; shift 2 ;;
            --repair)
                ARG_REPAIR=true; shift ;;
            --no-migrate)
                ARG_NO_MIGRATE=true; shift ;;
            --)
                shift
                ARG_MANAGE_CMD="$*"
                break ;;
            -h|--help)
                sed -n '/^# Usage/,/^# =/p' "$0" | sed 's/^# \?//'
                exit 0 ;;
            *)
                die "Unknown argument: $1  (use --help for usage)" ;;
        esac
    done
}

# ---------------------------------------------------------------------------
# Python detection
# ---------------------------------------------------------------------------

find_python() {
    local candidate version_ok

    for candidate in python3 python python3.12 python3.11 python3.10 python3.9 python3.8; do
        if command -v "${candidate}" &>/dev/null; then
            version_ok=$(
                "${candidate}" - <<'PY'
import sys
ok = sys.version_info >= (3, 8)
print("yes" if ok else f"no:{sys.version_info.major}.{sys.version_info.minor}")
PY
            )
            if [[ "${version_ok}" == "yes" ]]; then
                echo "${candidate}"
                return 0
            else
                warn "Skipping ${candidate}: version ${version_ok#no:} < 3.8"
            fi
        fi
    done

    return 1
}

assert_python() {
    section "Python"
    local python_bin
    if ! python_bin="$(find_python)"; then
        die "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ not found on PATH.\n" \
            "       Install it from https://python.org and ensure it is on your PATH."
    fi
    PYTHON="${python_bin}"
    info "Python interpreter : $("${PYTHON}" --version)  (${PYTHON})"
}

# ---------------------------------------------------------------------------
# Dependency installation
# ---------------------------------------------------------------------------

run_installer() {
    section "Dependencies"
    local installer="${SCRIPT_DIR}/setup_installer.py"

    [[ -f "${installer}" ]] || die "setup_installer.py not found at ${installer}."

    local installer_args=()
    [[ "${ARG_REPAIR}" == true ]] && installer_args+=("--repair")

    info "Running dependency installer …"
    if ! "${PYTHON}" "${installer}" "${installer_args[@]}"; then
        die "Dependency installation failed.\n" \
            "       Review ${SCRIPT_DIR}/installer.log for details.\n" \
            "       Try running:  ${PYTHON} setup_installer.py --repair"
    fi
}

# ---------------------------------------------------------------------------
# Virtual environment activation
# ---------------------------------------------------------------------------

activate_venv() {
    section "Virtual Environment"
    if [[ -f "${VENV_ACTIVATE}" ]]; then
        # shellcheck disable=SC1090
        source "${VENV_ACTIVATE}"
        info "Virtual environment activated: ${VENV_DIR}"
        detail "Python: $(python --version)"
        detail "pip   : $(pip --version 2>/dev/null || echo 'unavailable')"
    else
        warn "Virtual environment not found at ${VENV_DIR}."
        warn "Using system Python — this is not recommended for production."
    fi
}

# ---------------------------------------------------------------------------
# Environment file validation
# ---------------------------------------------------------------------------

check_env_file() {
    section "Environment Configuration"
    if [[ ! -f "${ENV_FILE}" ]]; then
        warn ".env file not found at ${ENV_FILE}."
        warn "The application requires environment variables for:"
        detail "  SECRET_KEY, database credentials, API keys (Stripe, M-Pesa, etc.)"
        warn "Copy .env.example to .env and fill in your values before proceeding."

        # Allow the server to start in development with defaults,
        # but refuse in production.
        if [[ "${ARG_SETTINGS}" == *production* ]]; then
            die ".env is mandatory for the production settings module."
        fi
    else
        info ".env file found  ✔"
    fi

    export DJANGO_SETTINGS_MODULE="${ARG_SETTINGS}"
    info "Django settings : ${DJANGO_SETTINGS_MODULE}"
}

# ---------------------------------------------------------------------------
# Early runtime directory bootstrap
# ---------------------------------------------------------------------------
# The Django logging configuration uses a RotatingFileHandler that opens
# logs/Echo_Solutions.log at import time.  If the logs/ directory does not
# exist yet the server crashes before a single line of application code runs.
# We create all three runtime directories here — before the installer, before
# venv activation, before migrations — so the application always finds them.

bootstrap_runtime_dirs() {
    local -a dirs=("${LOG_DIR}" "${MEDIA_DIR}" "${STATIC_DIR}")
    local dir any_created=0

    for dir in "${dirs[@]}"; do
        if [[ ! -d "${dir}" ]]; then
            if mkdir -p "${dir}" 2>/dev/null; then
                info "Bootstrap: created ${dir}"
                (( any_created++ )) || true
            else
                warn "Bootstrap: could not create ${dir} — check filesystem permissions."
            fi
        fi
    done

    if (( any_created == 0 )); then
        detail "Bootstrap: all runtime directories already present."
    fi
}

# ---------------------------------------------------------------------------
# Runtime directory setup (section-level reporting, post-venv)
# ---------------------------------------------------------------------------

ensure_directories() {
    section "Runtime Directories"
    local dir created=0
    for dir in "${LOG_DIR}" "${MEDIA_DIR}" "${STATIC_DIR}"; do
        if [[ ! -d "${dir}" ]]; then
            # Should rarely fire — bootstrap_runtime_dirs() ran earlier.
            mkdir -p "${dir}"
            info "Created: ${dir}"
            (( created++ )) || true
        fi
    done
    [[ "${created}" -eq 0 ]] && info "All runtime directories present  ✔"
}

# ---------------------------------------------------------------------------
# Database migrations
# ---------------------------------------------------------------------------

run_migrations() {
    if [[ "${ARG_NO_MIGRATE}" == true ]]; then
        warn "Skipping migrations (--no-migrate was set)."
        return
    fi

    section "Database Migrations"
    info "Applying migrations …"

    if ! python manage.py migrate --run-syncdb 2>&1; then
        die "Database migrations failed.\n" \
            "       Common causes:\n" \
            "         • DATABASE_URL / DB_* variables not set in .env\n" \
            "         • Database server not running\n" \
            "         • Migration conflict — try: python manage.py migrate --fake-initial"
    fi

    info "Migrations applied  ✔"
}

# ---------------------------------------------------------------------------
# Management command passthrough
# ---------------------------------------------------------------------------

run_management_command() {
    section "Management Command"
    info "Running: python manage.py ${ARG_MANAGE_CMD}"
    # Word-splitting is intentional here — the user supplied the command.
    # shellcheck disable=SC2086
    exec python manage.py ${ARG_MANAGE_CMD}
}

# ---------------------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------------------

start_server() {
    section "Development Server"

    # Validate port is numeric
    if ! [[ "${ARG_PORT}" =~ ^[0-9]+$ ]] || \
       (( ARG_PORT < 1 || ARG_PORT > 65535 )); then
        die "Invalid port: ${ARG_PORT}  (must be 1–65535)"
    fi

    # Warn if binding to all interfaces in a potentially insecure way
    if [[ "${ARG_HOST}" == "0.0.0.0" ]]; then
        warn "Binding to 0.0.0.0 — server is accessible from the network."
        warn "Do not use this in a production environment without a reverse proxy."
    fi

    info "Starting Django development server …"
    info "  Address  :  http://${ARG_HOST}:${ARG_PORT}/"
    info "  Settings :  ${DJANGO_SETTINGS_MODULE}"
    info "  Press Ctrl-C to stop."
    echo ""

    exec python manage.py runserver "${ARG_HOST}:${ARG_PORT}"
}

# ---------------------------------------------------------------------------
# Cleanup on unexpected exit
# ---------------------------------------------------------------------------

_on_exit() {
    local code=$?
    if (( code != 0 )); then
        echo ""
        error "Script exited with code ${code}."
        detail "Check ${SCRIPT_DIR}/installer.log for installer details."
        detail "Check ${LOG_DIR}/Echo_Solutions.log for application details."
    fi
}
trap _on_exit EXIT

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    cd "${SCRIPT_DIR}"
    parse_args "$@"

    # Create runtime directories unconditionally before any other step.
    # Django's RotatingFileHandler opens logs/ at import time — if the
    # directory is absent the server crashes before printing a single line.
    bootstrap_runtime_dirs

    print_banner

    assert_python
    run_installer
    activate_venv
    check_env_file
    ensure_directories

    if [[ -n "${ARG_MANAGE_CMD}" ]]; then
        run_management_command
        # exec replaces the shell — we never return here
    fi

    run_migrations
    start_server
    # exec replaces the shell — we never return here
}

main "$@"