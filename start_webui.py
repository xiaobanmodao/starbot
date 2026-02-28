from __future__ import annotations

import sys
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
        elif arg == "--no-browser":
            opts["open_browser"] = False
        i += 1
    return opts


def main():
    import start as _start
    from comms.webui_server import WebUiServer

    cli = _parse_cli(sys.argv[1:])
    _start.print_banner()
    print("  >> Web UI mode\n")

    if not _start._ensure_bootstrap_deps_for_config():
        input("\nPress Enter to exit...")
        sys.exit(1)

    from config import setup

    if cli["setup_only"]:
        setup(force=True)
        return
    if cli["force_setup"]:
        setup(force=True)
    else:
        setup()

    server = WebUiServer(host=str(cli["host"]), port=int(cli["port"]))
    server.start()
    print(f"  Web UI started: {server.url}")
    if bool(cli["open_browser"]):
        try:
            webbrowser.open(server.url)
        except Exception:
            pass
    print("  Press Ctrl+C to stop.")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
