from __future__ import annotations

import os
import sys


def _parse_cli(argv: list[str]) -> dict[str, bool]:
    opts = {"force_setup": False, "setup_only": False}
    for raw in argv:
        arg = (raw or "").strip().lower()
        if arg in {"setup", "config"}:
            opts["force_setup"] = True
            opts["setup_only"] = True
        elif arg in {"--setup", "--config", "--wizard"}:
            opts["force_setup"] = True
        elif arg in {"--setup-only", "--config-only", "--wizard-only"}:
            opts["force_setup"] = True
            opts["setup_only"] = True
    return opts


def main():
    # Reuse startup bootstrap helpers; this does not start Discord.
    import start as _start

    os.chdir(_start._DIR)
    cli = _parse_cli(sys.argv[1:])

    _start.print_banner()
    print("  >> GUI mode\n")

    if not _start._ensure_bootstrap_deps_for_config():
        input("\nPress Enter to exit...")
        sys.exit(1)

    from config import setup

    if cli["setup_only"]:
        print("  Running configuration wizard only (no GUI startup).")
        setup(force=True)
        return

    if cli["force_setup"]:
        setup(force=True)
    else:
        setup()

    from comms.gui_client import launch_gui

    launch_gui()


if __name__ == "__main__":
    main()

