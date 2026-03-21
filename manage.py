#!/usr/bin/env python
"""Echo_Solutions – Django Management Utility."""
import os, sys

def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Echo_Solutions.settings.development")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Could not import Django.") from exc
    execute_from_command_line(sys.argv)

if __name__ == "__main__":
    main()
