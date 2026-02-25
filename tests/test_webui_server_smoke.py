from __future__ import annotations

import importlib

def test_webui_server_module_imports_and_builds_handler():
    mod = importlib.import_module("comms.webui_server")
    class FakeService:
        pass

    server = mod.WebUiServer(service=FakeService(), port=0)
    handler = server._build_handler()
    assert handler is not None
    assert hasattr(handler, "service_factory")


def test_start_webui_parse_cli():
    mod = importlib.import_module("start_webui")
    assert mod._parse_cli(["setup"])["setup_only"] is True
    assert mod._parse_cli(["--setup"])["force_setup"] is True
    parsed = mod._parse_cli(["--host", "0.0.0.0", "--port", "9999", "--no-browser"])
    assert parsed["host"] == "0.0.0.0"
    assert parsed["port"] == 9999
    assert parsed["open_browser"] is False
