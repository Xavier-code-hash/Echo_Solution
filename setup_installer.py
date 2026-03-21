#!/usr/bin/env python3
"""
Echo Solutions — Dependency Installer
======================================
Cross-platform bootstrap script for Python 3.8+.

Responsibilities
----------------
  1. Validate the host Python version.
  2. Create (or reuse) a project-local virtual environment.
  3. Upgrade pip / setuptools / wheel inside the venv.
  4. Install every package listed in requirements.txt.
  5. Verify the installation by cross-referencing pip freeze output.
  6. Emit a structured, timestamped log to installer.log.

Exit codes
----------
  0  All steps completed successfully.
  1  Fatal error — details in installer.log.
  2  Verification failed after installation.
  3  requirements.txt not found.
  4  Python version below the minimum requirement.

Usage
-----
  python setup_installer.py              # install + verify
  python setup_installer.py --repair     # force-reinstall everything
  python setup_installer.py --check      # verify only, no installation
  python setup_installer.py --verbose    # show subprocess stdout/stderr
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, NoReturn, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT      = Path(__file__).resolve().parent
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
VENV_DIR          = PROJECT_ROOT / ".venv"
LOG_FILE          = PROJECT_ROOT / "installer.log"
MIN_PYTHON        = (3, 8)
PIP_UPGRADE_PKGS  = ("pip", "setuptools", "wheel")

# Timeout in seconds for each pip subprocess call.
# Large packages (e.g. Pillow) can take time on slow connections.
SUBPROCESS_TIMEOUT = 300


# ---------------------------------------------------------------------------
# Exit-code sentinels
# ---------------------------------------------------------------------------

class ExitCode:
    OK                  = 0
    FATAL               = 1
    VERIFY_FAILED       = 2
    REQUIREMENTS_MISSING = 3
    PYTHON_TOO_OLD      = 4


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _build_logger(verbose: bool) -> logging.Logger:
    """
    Construct a logger that writes to both the log file and stdout.
    File handler always records at DEBUG level; console respects --verbose.
    """
    fmt       = "%(asctime)s [%(levelname)-8s] %(message)s"
    datefmt   = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)

    logger = logging.getLogger("echo_installer")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Avoid duplicate handlers on repeated calls in test environments
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


# Module-level logger; reconfigured after arg-parsing.
log: logging.Logger = logging.getLogger("echo_installer")


# ---------------------------------------------------------------------------
# Operating system helpers
# ---------------------------------------------------------------------------

def current_os() -> str:
    """Return a normalised OS identifier: 'windows', 'macos', or 'linux'."""
    return {"Windows": "windows", "Darwin": "macos"}.get(platform.system(), "linux")


def venv_python() -> Path:
    """Absolute path to the venv Python interpreter."""
    return (
        VENV_DIR / "Scripts" / "python.exe"
        if current_os() == "windows"
        else VENV_DIR / "bin" / "python"
    )


def venv_pip() -> Path:
    """Absolute path to the venv pip executable."""
    return (
        VENV_DIR / "Scripts" / "pip.exe"
        if current_os() == "windows"
        else VENV_DIR / "bin" / "pip"
    )


# ---------------------------------------------------------------------------
# Subprocess wrapper
# ---------------------------------------------------------------------------

@dataclass
class CommandResult:
    returncode: int
    stdout:     str
    stderr:     str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(
    cmd: Sequence[str | Path],
    *,
    capture: bool = False,
    timeout: int  = SUBPROCESS_TIMEOUT,
    env: dict | None = None,
) -> CommandResult:
    """
    Execute *cmd* in a subprocess.

    Parameters
    ----------
    cmd:
        Iterable of command parts (no shell=True).
    capture:
        When True, stdout and stderr are captured and returned in
        CommandResult rather than printed to the terminal.
    timeout:
        Kill the subprocess after this many seconds and raise
        SubprocessTimeout.
    env:
        Optional environment mapping passed to the child process.
        Defaults to the current process environment.

    Raises
    ------
    SubprocessTimeout   if the process exceeds *timeout* seconds.
    SubprocessError     if the process exits with a non-zero code.
    """
    str_cmd = [str(c) for c in cmd]
    log.debug("$ %s", " ".join(str_cmd))

    try:
        proc = subprocess.run(
            str_cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
            env=env or os.environ.copy(),
        )
    except subprocess.TimeoutExpired as exc:
        raise SubprocessTimeout(
            f"Command timed out after {timeout}s: {' '.join(str_cmd)}"
        ) from exc
    except FileNotFoundError as exc:
        raise SubprocessError(
            f"Executable not found: {str_cmd[0]}"
        ) from exc
    except OSError as exc:
        raise SubprocessError(
            f"OS error running {str_cmd[0]}: {exc}"
        ) from exc

    result = CommandResult(proc.returncode, proc.stdout or "", proc.stderr or "")

    if not result.ok:
        raise SubprocessError(
            f"Command exited {result.returncode}: {' '.join(str_cmd)}\n"
            f"stdout: {result.stdout.strip()}\n"
            f"stderr: {result.stderr.strip()}"
        )

    return result


class SubprocessError(RuntimeError):
    """Raised when a child process exits with a non-zero return code."""


class SubprocessTimeout(SubprocessError):
    """Raised when a child process exceeds its allotted timeout."""


# ---------------------------------------------------------------------------
# Progress / UI helpers
# ---------------------------------------------------------------------------

def banner(message: str) -> None:
    """Emit a prominent section banner to the logger."""
    width = 64
    bar   = "─" * width
    log.info(bar)
    log.info("  %s", message)
    log.info(bar)


@contextlib.contextmanager
def step(description: str) -> Iterator[None]:
    """
    Context manager that logs the start and end of a logical step,
    including elapsed time, and converts any exception into a fatal log entry.
    """
    log.info("▶  %s …", description)
    start = time.monotonic()
    try:
        yield
    except (SubprocessError, SubprocessTimeout) as exc:
        elapsed = time.monotonic() - start
        log.error("✗  %s — FAILED (%.1fs)", description, elapsed)
        log.error("   %s", exc)
        raise
    except Exception as exc:
        elapsed = time.monotonic() - start
        log.error("✗  %s — UNEXPECTED ERROR (%.1fs): %s", description, elapsed, exc)
        raise
    else:
        elapsed = time.monotonic() - start
        log.info("✔  %s (%.1fs)", description, elapsed)


def fatal(message: str, code: int = ExitCode.FATAL) -> NoReturn:
    """Log a fatal error and exit with *code*."""
    log.critical("FATAL: %s", message)
    log.critical("See %s for full details.", LOG_FILE)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Python version guard
# ---------------------------------------------------------------------------

def assert_python_version() -> None:
    """Abort immediately if the host interpreter is too old."""
    if sys.version_info < MIN_PYTHON:
        fatal(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required. "
            f"This interpreter is {platform.python_version()} "
            f"({sys.executable}).",
            ExitCode.PYTHON_TOO_OLD,
        )
    log.info(
        "Python %s  [%s]  ✔",
        platform.python_version(),
        sys.executable,
    )


# ---------------------------------------------------------------------------
# Virtual environment
# ---------------------------------------------------------------------------

def ensure_venv() -> None:
    """
    Create the project-local virtual environment if it does not already exist.

    The check is done on the Python executable inside the venv, not the
    directory itself — this correctly handles the case where .venv exists
    but was partially constructed by a previous interrupted run.
    """
    if venv_python().is_file():
        log.info("Virtual environment  →  %s  ✔", VENV_DIR)
        return

    log.info("Creating virtual environment at %s …", VENV_DIR)

    # Remove a corrupt / incomplete venv directory before recreating.
    if VENV_DIR.exists():
        log.warning("Removing incomplete venv at %s", VENV_DIR)
        shutil.rmtree(VENV_DIR, ignore_errors=True)

    try:
        run([sys.executable, "-m", "venv", "--upgrade-deps", str(VENV_DIR)])
    except SubprocessError as exc:
        # --upgrade-deps was added in Python 3.9; fall back for 3.8.
        log.debug("--upgrade-deps not supported, retrying without it: %s", exc)
        run([sys.executable, "-m", "venv", str(VENV_DIR)])

    if not venv_python().is_file():
        fatal(
            f"venv was created but the Python executable is missing at "
            f"{venv_python()}.  The venv module may be broken on this system. "
            f"Try: {sys.executable} -m pip install virtualenv && "
            f"virtualenv {VENV_DIR}",
        )

    log.info("Virtual environment created  ✔")


# ---------------------------------------------------------------------------
# pip management
# ---------------------------------------------------------------------------

def upgrade_pip() -> None:
    """
    Upgrade pip, setuptools, and wheel inside the venv.

    A failure here is non-fatal — older versions of these tools still work
    for most packages.  We log a warning and continue.
    """
    log.info("Upgrading pip / setuptools / wheel …")
    try:
        run([
            str(venv_python()), "-m", "pip", "install",
            "--quiet", "--upgrade",
            *PIP_UPGRADE_PKGS,
        ])
        log.info("pip / setuptools / wheel upgraded  ✔")
    except (SubprocessError, SubprocessTimeout) as exc:
        log.warning(
            "pip upgrade failed (non-fatal — continuing with existing version): %s",
            exc,
        )


# ---------------------------------------------------------------------------
# Requirements parsing
# ---------------------------------------------------------------------------

@dataclass
class Requirement:
    raw:  str            # original line from requirements.txt
    name: str            # normalised package name (lower, underscores)
    spec: str            # version specifier, e.g. "==4.2.29"

    @classmethod
    def parse(cls, line: str) -> "Requirement":
        # Strip inline comments
        line = re.split(r"\s+#", line)[0].strip()
        # Extract bare name, normalise separators
        match = re.match(r"^([A-Za-z0-9_.\-]+)", line)
        name  = match.group(1) if match else line
        spec  = line[len(name):]
        return cls(raw=line, name=re.sub(r"[-.]", "_", name).lower(), spec=spec)


def load_requirements() -> list[Requirement]:
    """
    Parse requirements.txt and return a list of Requirement objects.
    Skips blank lines, comment lines, and -r / -c include directives.
    """
    if not REQUIREMENTS_FILE.is_file():
        fatal(
            f"requirements.txt not found at {REQUIREMENTS_FILE}.  "
            f"Ensure you are running this script from the project root.",
            ExitCode.REQUIREMENTS_MISSING,
        )

    reqs: list[Requirement] = []
    with REQUIREMENTS_FILE.open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith(("#", "-r", "-c", "--")):
                continue
            try:
                reqs.append(Requirement.parse(line))
            except Exception as exc:
                log.warning("requirements.txt line %d skipped (%s): %r", lineno, exc, line)

    if not reqs:
        fatal("requirements.txt is empty or contains no installable packages.")

    log.info("Loaded %d packages from requirements.txt", len(reqs))
    return reqs


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

def install_packages(reqs: list[Requirement], *, force: bool = False) -> None:
    """
    Install all requirements from requirements.txt.

    Strategy
    --------
    1. Attempt a single bulk install — fastest path for clean environments.
    2. On failure, fall back to per-package installs to isolate the culprit.
    3. Report every failed package clearly before aborting.
    """
    pip   = str(venv_pip())
    label = " (force-reinstall)" if force else ""

    log.info("Installing %d packages%s …", len(reqs), label)

    bulk_cmd = [pip, "install", "--progress-bar", "off"]
    if force:
        bulk_cmd.append("--force-reinstall")
    bulk_cmd += ["-r", str(REQUIREMENTS_FILE)]

    try:
        run(bulk_cmd, timeout=SUBPROCESS_TIMEOUT * 3)
        log.info("Bulk install succeeded  ✔")
        return
    except (SubprocessError, SubprocessTimeout) as exc:
        log.warning("Bulk install failed — switching to per-package fallback:")
        log.warning("  %s", exc)

    _install_individually(reqs, pip, force=force)


def _install_individually(
    reqs:  list[Requirement],
    pip:   str,
    *,
    force: bool = False,
) -> None:
    """
    Install each package independently.
    Collects all failures before aborting so the full error picture is visible.
    """
    failed: list[tuple[Requirement, str]] = []

    for req in reqs:
        cmd = [pip, "install", "--progress-bar", "off"]
        if force:
            cmd.append("--force-reinstall")
        cmd.append(req.raw)

        try:
            run(cmd)
            log.info("  ✔  %-40s", req.raw)
        except SubprocessTimeout as exc:
            log.error("  ✗  %-40s  [TIMEOUT]", req.raw)
            failed.append((req, f"timed out: {exc}"))
        except SubprocessError as exc:
            log.error("  ✗  %-40s  [FAILED]", req.raw)
            failed.append((req, str(exc)))

    if failed:
        log.error("")
        log.error("%d package(s) could not be installed:", len(failed))
        for req, reason in failed:
            log.error("    %-40s  →  %s", req.raw, reason.splitlines()[0])
        log.error("")
        log.error(
            "Possible causes:\n"
            "  • No internet connection\n"
            "  • Package requires system-level build tools (gcc, libssl-dev, etc.)\n"
            "  • Version conflict with another installed package\n"
            "  • Package name misspelled in requirements.txt\n"
            "Run with --verbose for full subprocess output."
        )
        fatal(
            f"{len(failed)} package(s) failed to install.  "
            f"See above for details.",
        )

    log.info("All packages installed via per-package fallback  ✔")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

@dataclass
class VerifyReport:
    found:   list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing


def verify_installation(reqs: list[Requirement]) -> VerifyReport:
    """
    Cross-reference requirements.txt against pip freeze output.

    Uses normalised names (lower-case, hyphens→underscores) to handle
    packages whose distribution name differs from their import name.
    """
    pip = str(venv_pip())
    log.info("Verifying installed packages …")

    try:
        result = run([pip, "list", "--format=freeze"], capture=True)
    except SubprocessError as exc:
        log.error("Could not run pip list: %s", exc)
        return VerifyReport(missing=[r.raw for r in reqs])

    installed: set[str] = set()
    for line in result.stdout.splitlines():
        if "==" in line:
            pkg = line.split("==")[0].strip()
            installed.add(re.sub(r"[-.]", "_", pkg).lower())

    report = VerifyReport()
    for req in reqs:
        if req.name in installed:
            log.info("  ✔  %-40s", req.raw)
            report.found.append(req.raw)
        else:
            log.warning("  ✗  %-40s  [NOT FOUND]", req.raw)
            report.missing.append(req.raw)

    log.info(
        "Verification complete: %d/%d packages confirmed.",
        len(report.found),
        len(reqs),
    )
    return report


# ---------------------------------------------------------------------------
# Django post-install checks
# ---------------------------------------------------------------------------

def check_env_file() -> None:
    """
    Warn if no .env file is present.
    Echo Solutions requires environment variables for secret keys,
    database credentials, and third-party API keys.
    """
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        log.warning(
            ".env file not found at %s.  "
            "Copy .env.example to .env and fill in your credentials "
            "before starting the server.",
            env_path,
        )
    else:
        log.info(".env file found  ✔")


def check_logs_directory() -> None:
    """Create the logs/ directory that Django's RotatingFileHandler expects."""
    logs_dir = PROJECT_ROOT / "logs"
    if not logs_dir.is_dir():
        logs_dir.mkdir(parents=True, exist_ok=True)
        log.info("Created logs/ directory  ✔")
    else:
        log.info("logs/ directory present  ✔")


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def _handle_interrupt(signum: int, frame: object) -> NoReturn:
    """Graceful SIGINT / SIGTERM handler — ensure the log file is flushed."""
    log.warning("Installation interrupted by signal %d — partial state may remain.", signum)
    log.warning("Re-run this script (or use --repair) to complete setup.")
    sys.exit(ExitCode.FATAL)


signal.signal(signal.SIGINT,  _handle_interrupt)
signal.signal(signal.SIGTERM, _handle_interrupt)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog        = "setup_installer.py",
        description = "Echo Solutions — dependency bootstrap and environment verifier",
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog = (
            "Exit codes:\n"
            "  0  Success\n"
            "  1  Fatal error\n"
            "  2  Verification failed\n"
            "  3  requirements.txt not found\n"
            "  4  Python version too old\n"
        ),
    )
    parser.add_argument(
        "--repair",
        action  = "store_true",
        help    = "Force-reinstall every package regardless of current state",
    )
    parser.add_argument(
        "--check",
        action  = "store_true",
        help    = "Verify the environment without installing anything",
    )
    parser.add_argument(
        "--verbose", "-v",
        action  = "store_true",
        help    = "Show subprocess stdout/stderr in the console",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    global log
    log = _build_logger(verbose=args.verbose)

    banner("Echo Solutions — Dependency Installer")
    log.info("Timestamp   : %s", time.strftime("%Y-%m-%d %H:%M:%S %Z"))
    log.info("OS          : %s  (%s)", current_os(), platform.platform())
    log.info("Project root: %s", PROJECT_ROOT)
    log.info("Log file    : %s", LOG_FILE)
    log.info("Mode        : %s", "check" if args.check else "repair" if args.repair else "install")

    assert_python_version()

    reqs = load_requirements()

    if args.check:
        banner("Check mode — verifying existing environment")
        with step("Locating virtual environment"):
            ensure_venv()
        report = verify_installation(reqs)
        if report.ok:
            banner("✔  Environment is healthy — all packages present")
            sys.exit(ExitCode.OK)
        else:
            log.error(
                "%d missing package(s): %s",
                len(report.missing),
                ", ".join(report.missing),
            )
            log.error("Run without --check to install them.")
            sys.exit(ExitCode.VERIFY_FAILED)

    # Full install path
    try:
        with step("Creating virtual environment"):
            ensure_venv()

        with step("Upgrading pip / setuptools / wheel"):
            upgrade_pip()

        with step("Installing project dependencies"):
            install_packages(reqs, force=args.repair)

    except (SubprocessError, SubprocessTimeout) as exc:
        fatal(f"Installation step failed: {exc}")
    except Exception as exc:
        fatal(f"Unexpected error during installation: {exc}")

    banner("Verification")
    report = verify_installation(reqs)

    check_env_file()
    check_logs_directory()

    if report.ok:
        banner("✔  Setup complete — all dependencies satisfied")
        log.info("")
        log.info("Next steps:")
        log.info("  1. Ensure .env is configured with your credentials.")
        if current_os() == "windows":
            log.info("  2. Activate venv :  .venv\\Scripts\\activate")
        else:
            log.info("  2. Activate venv :  source .venv/bin/activate")
        log.info("  3. Apply migrations:  python manage.py migrate")
        log.info("  4. Start server   :  python manage.py runserver")
        sys.exit(ExitCode.OK)
    else:
        log.error(
            "%d package(s) failed verification: %s",
            len(report.missing),
            ", ".join(report.missing),
        )
        log.error("Run with --repair to force-reinstall all packages.")
        sys.exit(ExitCode.VERIFY_FAILED)


if __name__ == "__main__":
    main()