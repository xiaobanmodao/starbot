"""Desktop entrypoint wrapper."""
from __future__ import annotations

import sys


def _parse_cli(argv: list[str]) -> dict[str, object]:
    opts: dict[str, object] = {
        "force_setup": False,
        "setup_only": False,
        "host": "127.0.0.1",
        "port": 8765,
        "width": 1280,
        "height": 820,
        "maximized": False,
        "debug_webview": False,
    }
    i = 0
    while i < len(argv):
        arg = (argv[i] or "").strip().lower()
        if arg in {"setup", "config"}:
            opts["force_setup"] = True
            opts["setup_only"] = True
        elif arg in {"--setup", "--config", "--wizard"}:
            opts["force_setup"] = True
        elif arg in {"--setup-only", "--config-only", "--wizard-only"}:
            opts["force_setup"] = True
            opts["setup_only"] = True
        elif arg == "--host" and i + 1 < len(argv):
            opts["host"] = argv[i + 1]
            i += 1
        elif arg == "--port" and i + 1 < len(argv):
            try:
                opts["port"] = int(argv[i + 1])
            except ValueError:
                pass
            i += 1
        elif arg == "--width" and i + 1 < len(argv):
            try:
                opts["width"] = int(argv[i + 1])
            except ValueError:
                pass
            i += 1
        elif arg == "--height" and i + 1 < len(argv):
            try:
                opts["height"] = int(argv[i + 1])
            except ValueError:
                pass
            i += 1
        elif arg == "--maximized":
            opts["maximized"] = True
        elif arg == "--debug-webview":
            opts["debug_webview"] = True
        i += 1
    return opts


def _ensure_desktop_webview_dep(start_mod) -> bool:
    if start_mod._can_import("webview"):
        return True
    return bool(start_mod._pip_install(["pywebview>=5.4"]))


def _attach_close_handler(window, on_close) -> None:
    try:
        window.events.closed += on_close
    except Exception:
        # Best effort only: some backends may not expose close events.
        pass


def main():
    _ = _parse_cli(sys.argv[1:])
    # Keep behavior simple: desktop mode reuses start.py flow.
    import start

    start.main()


if __name__ == "__main__":
    main()
