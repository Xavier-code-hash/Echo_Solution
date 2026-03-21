#!/usr/bin/env bash
# ============================================================
# run.sh — macOS / Linux launcher
# Runs setup_installer.py then starts the Django application.
# ============================================================
set -euo pipefail

# ── Colours ─────────────────────────────────────────────────
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
RESET="\033[0m"

info()  { echo -e "${GREEN}[INFO]${RESET}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error() { echo -e "${RED}[ERROR]${RESET} $*"; }

# ── Move to script directory ─────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║     Dependency Installer (Unix/macOS)    ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ── 1. Ensure Python 3 is available ──────────────────────────
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c "import sys; print(sys.version_info >= (3,8))")
        if [[ "$version" == "True" ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON" ]]; then
    error "Python 3.8+ not found. Please install it and re-run this script."
    exit 1
fi
info "Using Python: $($PYTHON --version)"

# ── 2. Run the installer ─────────────────────────────────────
info "Running dependency installer …"
"$PYTHON" setup_installer.py || {
    error "Installer failed. Check installer.log for details."
    exit 1
}

# ── 3. Activate virtual environment ──────────────────────────
VENV_ACTIVATE="$SCRIPT_DIR/.venv/bin/activate"
if [[ -f "$VENV_ACTIVATE" ]]; then
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE"
    info "Virtual environment activated."
else
    warn "Virtual environment not found — using system Python."
fi

# ── 4. Apply Django migrations ───────────────────────────────
info "Applying database migrations …"
python manage.py migrate --run-syncdb

# ── 5. Start the Django app ───────────────────────────────────
info "Starting Django development server …"
python manage.py runserver
