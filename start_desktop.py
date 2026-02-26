"""Convenience shortcut: launch Starbot in Desktop (Electron) mode."""
from __future__ import annotations

import sys


def main():
    # Inject --desktop so start.py skips the interactive menu
    if "--desktop" not in sys.argv:
        sys.argv.insert(1, "--desktop")

    import start
    start.main()


if __name__ == "__main__":
    main()
