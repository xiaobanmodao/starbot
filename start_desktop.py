from __future__ import annotations

import os
import sys
from typing import Any


def _parse_cli(argv: list[str]) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "force_setup": False,
        "setup_only": False,
        "host": "127.0.0.1",
        "port": 8765,
        "width": 1440,
        "height": 940,
        "min_width": 1100,
        "min_height": 760,
        "title": "Starbot",
        "maximized": False,
        "debug_webview": False,
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
        elif low == "--width" and i + 1 < len(argv):
            try:
                opts["width"] = max(800, int(argv[i + 1]))
            except ValueError:
                pass
            i += 1
        elif low == "--height" and i + 1 < len(argv):
            try:
                opts["height"] = max(600, int(argv[i + 1]))
            except ValueError:
                pass
            i += 1
        elif low == "--title" and i + 1 < len(argv):
            opts["title"] = argv[i + 1] or opts["title"]
            i += 1
        elif low == "--maximized":
            opts["maximized"] = True
        elif low in {"--debug-webview", "--devtools"}:
            opts["debug_webview"] = True
        i += 1
    return opts


def _ensure_desktop_webview_dep(start_mod) -> bool:
    """Ensure the desktop WebView wrapper dependency is available."""
    if start_mod._can_import("webview"):
        return True

    print("  Missing desktop runtime dependency: pywebview")
    print("  Installing pywebview so the desktop client can start...")
    ok = start_mod._pip_install(["pywebview>=5.4"])
    if ok:
        print("  OK  pywebview installed\n")
    else:
        print("  ERROR Failed to install pywebview; cannot start desktop client.\n")
    return ok


def _attach_close_handler(window, on_close) -> None:
    """Best-effort hook for pywebview close events across versions."""
    try:
        events = getattr(window, "events", None)
        closed = getattr(events, "closed", None)
        if closed is not None:
            closed += on_close
            return
    except Exception:
        pass


def main():
    import start as _start

    os.chdir(_start._DIR)
    cli = _parse_cli(sys.argv[1:])

    _start.print_banner()
    print("  >> Desktop UI mode (native window + Web UI frontend)\n")

    if not _start._ensure_bootstrap_deps_for_config():
        input("\nPress Enter to exit...")
        sys.exit(1)

    from config import setup

    if cli["setup_only"]:
        print("  Running configuration wizard only (no Desktop UI startup).")
        print("  Tip: 'Skip / Modify' appears only when a step is already fully configured.\n")
        setup(force=True)
        return

    if cli["force_setup"]:
        setup(force=True)
    else:
        setup()

    if not _start._run_section("Core Python dependencies", _start.install_core_deps):
        input("\nPress Enter to exit...")
        sys.exit(1)
    _start._run_section("Playwright Chromium", _start.install_playwright_browser)
    _start._run_section("External tools", _start.check_external_tools)
    _start._run_section("Skill dependencies", _start.check_skill_deps)
    _start._run_section("Initialize directories", _start.check_dirs)

    if not _start._run_section("Desktop WebView runtime", _ensure_desktop_webview_dep, _start):
        input("\nPress Enter to exit...")
        sys.exit(1)

    from comms.webui_server import WebUiServer
    import webview  # type: ignore

    server = WebUiServer(host=str(cli["host"]), port=int(cli["port"]))
    server.start()

    print(f"  Desktop UI local service: {server.url}")
    print("  Discord mode remains available via `python start.py`.")
    print("  Close the desktop window to stop the local service.\n")

    stopped = False

    def _stop_server():
        nonlocal stopped
        if stopped:
            return
        stopped = True
        try:
            server.stop()
        except Exception:
            pass

    try:
        window = webview.create_window(
            str(cli["title"]),
            server.url,
            width=int(cli["width"]),
            height=int(cli["height"]),
            min_size=(int(cli["min_width"]), int(cli["min_height"])),
            maximized=bool(cli["maximized"]),
            resizable=True,
        )
        _attach_close_handler(window, _stop_server)
        webview.start(debug=bool(cli["debug_webview"]))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"  ERROR Failed to start desktop window: {e}")
        print("  Tip: Install Microsoft Edge WebView2 Runtime if not present.")
        input("\nPress Enter to exit...")
        sys.exit(1)
    finally:
        _stop_server()


if __name__ == "__main__":
    main()
