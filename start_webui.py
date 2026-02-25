from __future__ import annotations

import os
import sys
import time
import webbrowser


def _parse_cli(argv: list[str]) -> dict[str, object]:
    opts: dict[str, object] = {
        "force_setup": False,
        "setup_only": False,
        "host": "127.0.0.1",
        "port": 8765,
        "open_browser": True,
    }
    i = 0
    while i < len(argv):
        raw = argv[i]
        arg = (raw or "").strip()
        low = arg.lower()
        if low in {"setup", "config"}:
            opts["force_setup"] = True
            opts["setup_only"] = True
        elif low in {"--setup", "--config", "--wizard"}:
            opts["force_setup"] = True
        elif low in {"--setup-only", "--config-only", "--wizard-only"}:
            opts["force_setup"] = True
            opts["setup_only"] = True
        elif low == "--host" and i + 1 < len(argv):
            opts["host"] = argv[i + 1]
            i += 1
        elif low == "--port" and i + 1 < len(argv):
            try:
                opts["port"] = int(argv[i + 1])
            except ValueError:
                pass
            i += 1
        elif low == "--no-browser":
            opts["open_browser"] = False
        i += 1
    return opts


def main():
    import start as _start

    os.chdir(_start._DIR)
    cli = _parse_cli(sys.argv[1:])

    _start.print_banner()
    print("  >> Web UI mode (Tauri/Electron-ready frontend shell)\n")

    if not _start._ensure_bootstrap_deps_for_config():
        input("\nPress Enter to exit...")
        sys.exit(1)

    from config import setup

    if cli["setup_only"]:
        print("  Running configuration wizard only (no Web UI startup).")
        print("  Tip: 'Skip / Modify' appears only when a step is already fully configured.\n")
        setup(force=True)
        return

    if cli["force_setup"]:
        setup(force=True)
    else:
        setup()

    # Reuse existing dependency checks so Web UI can start on fresh environments.
    if not _start._run_section("Core Python dependencies", _start.install_core_deps):
        input("\nPress Enter to exit...")
        sys.exit(1)
    _start._run_section("Playwright Chromium", _start.install_playwright_browser)
    _start._run_section("External tools", _start.check_external_tools)
    _start._run_section("Skill dependencies", _start.check_skill_deps)
    _start._run_section("Initialize directories", _start.check_dirs)

    from comms.webui_server import WebUiServer

    server = WebUiServer(host=str(cli["host"]), port=int(cli["port"]))
    server.start()

    print(f"  Web UI running at: {server.url}")
    print("  Discord mode remains available via `python start.py`.")
    print("  Press Ctrl+C to stop.\n")

    if cli["open_browser"]:
        try:
            webbrowser.open(server.url)
        except Exception:
            pass

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n  Stopping Web UI server...")
        server.stop()


if __name__ == "__main__":
    main()
