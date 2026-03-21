#!/usr/bin/env python3
"""
setup_installer.py
------------------
Cross-platform dependency installer and environment manager.
Automatically detects the OS, creates/validates a virtual environment,
upgrades pip, installs all requirements, and verifies each package.

Usage:
    python setup_installer.py            # Install / verify dependencies
    python setup_installer.py --repair   # Force-reinstall all packages
    python setup_installer.py --check    # Check status without installing
"""

import sys
import os
import subprocess
import platform
import argparse
import logging
from pathlib import Path

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
REQUIREMENTS_FILE = Path(__file__).parent / "requirements.txt"
VENV_DIR = Path(__file__).parent / ".venv"
LOG_FILE = Path(__file__).parent / "installer.log"
MIN_PYTHON = (3, 8)

# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def banner(msg: str) -> None:
    line = "─" * 60
    log.info(line)
    log.info(f"  {msg}")
    log.info(line)


def run(cmd: list, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command with consistent error handling."""
    log.debug("Running: %s", " ".join(str(c) for c in cmd))
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
    )


def detect_os() -> str:
    system = platform.system()
    return {"Windows": "windows", "Darwin": "macos"}.get(system, "linux")


def python_ok() -> bool:
    if sys.version_info < MIN_PYTHON:
        log.error(
            "Python %d.%d+ is required. Found %s.",
            *MIN_PYTHON,
            platform.python_version(),
        )
        return False
    log.info("Python version: %s ✔", platform.python_version())
    return True


# ──────────────────────────────────────────────
# Virtual environment
# ──────────────────────────────────────────────

def venv_python() -> Path:
    """Return the path to the venv Python executable."""
    os_name = detect_os()
    if os_name == "windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def venv_pip() -> Path:
    os_name = detect_os()
    if os_name == "windows":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"


def ensure_venv() -> None:
    """Create virtual environment if it doesn't already exist."""
    if venv_python().exists():
        log.info("Virtual environment found at: %s ✔", VENV_DIR)
        return

    log.info("Creating virtual environment at: %s", VENV_DIR)
    try:
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
        log.info("Virtual environment created ✔")
    except subprocess.CalledProcessError as exc:
        log.error("Failed to create virtual environment: %s", exc)
        sys.exit(1)


# ──────────────────────────────────────────────
# pip management
# ──────────────────────────────────────────────

def upgrade_pip() -> None:
    log.info("Upgrading pip …")
    try:
        run([str(venv_python()), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
        log.info("pip upgraded ✔")
    except subprocess.CalledProcessError as exc:
        log.warning("pip upgrade encountered an issue (non-fatal): %s", exc)


# ──────────────────────────────────────────────
# Requirements parsing
# ──────────────────────────────────────────────

def parse_requirements() -> list[str]:
    """Read requirements.txt, skip comments and blank lines."""
    if not REQUIREMENTS_FILE.exists():
        log.error("requirements.txt not found at: %s", REQUIREMENTS_FILE)
        sys.exit(1)

    packages = []
    with REQUIREMENTS_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                packages.append(line)
    log.info("Found %d packages in requirements.txt", len(packages))
    return packages


# ──────────────────────────────────────────────
# Installation
# ──────────────────────────────────────────────

def install_packages(force: bool = False) -> None:
    """Install all requirements, with optional force-reinstall."""
    packages = parse_requirements()
    pip = str(venv_pip())

    cmd = [pip, "install"]
    if force:
        cmd.append("--force-reinstall")
    cmd += ["-r", str(REQUIREMENTS_FILE)]

    log.info("Installing packages%s …", " (force reinstall)" if force else "")
    try:
        run(cmd)
        log.info("All packages installed ✔")
    except subprocess.CalledProcessError as exc:
        log.error("Installation failed: %s", exc)
        log.info("Attempting individual package installs to isolate failures …")
        _install_individually(packages, pip, force)


def _install_individually(packages: list[str], pip: str, force: bool) -> None:
    """Fallback: install each package one-by-one for granular error reporting."""
    failed = []
    for pkg in packages:
        cmd = [pip, "install"]
        if force:
            cmd.append("--force-reinstall")
        cmd.append(pkg)
        try:
            run(cmd)
            log.info("  ✔  %s", pkg)
        except subprocess.CalledProcessError:
            log.error("  ✗  FAILED: %s", pkg)
            failed.append(pkg)

    if failed:
        log.error("The following packages could not be installed:")
        for pkg in failed:
            log.error("    • %s", pkg)
        sys.exit(1)
    else:
        log.info("All packages installed via individual fallback ✔")


# ──────────────────────────────────────────────
# Verification
# ──────────────────────────────────────────────

def verify_packages() -> bool:
    """Check that every required package is importable / pip-visible."""
    packages = parse_requirements()
    pip = str(venv_pip())

    log.info("Verifying installed packages …")
    result = run([pip, "list", "--format=freeze"], capture=True)
    installed = {
        line.split("==")[0].lower().replace("-", "_")
        for line in result.stdout.splitlines()
        if "==" in line
    }

    all_ok = True
    for pkg in packages:
        name = pkg.split("==")[0].split(">=")[0].split("<=")[0].strip()
        normalised = name.lower().replace("-", "_")
        if normalised in installed:
            log.info("  ✔  %s", pkg)
        else:
            log.warning("  ✗  NOT FOUND: %s", pkg)
            all_ok = False

    return all_ok


# ──────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Automated dependency installer")
    parser.add_argument("--repair", action="store_true", help="Force-reinstall all packages")
    parser.add_argument("--check", action="store_true", help="Verify packages without installing")
    args = parser.parse_args()

    banner("Dependency Installer — starting")
    log.info("OS detected : %s (%s)", detect_os(), platform.platform())
    log.info("Project root: %s", Path(__file__).parent)

    if not python_ok():
        sys.exit(1)

    if args.check:
        banner("Check mode — verifying existing environment")
        ensure_venv()
        ok = verify_packages()
        sys.exit(0 if ok else 1)

    ensure_venv()
    upgrade_pip()
    install_packages(force=args.repair)

    banner("Verification")
    ok = verify_packages()

    if ok:
        banner("✔ Setup complete — all dependencies satisfied")
        log.info("Activate the environment with:")
        if detect_os() == "windows":
            log.info("    .venv\\Scripts\\activate")
        else:
            log.info("    source .venv/bin/activate")
    else:
        log.error("Some packages are missing. Run with --repair to force-reinstall.")
        sys.exit(1)


if __name__ == "__main__":
    main()
