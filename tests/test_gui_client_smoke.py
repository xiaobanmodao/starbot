from __future__ import annotations

import importlib


def test_gui_client_module_imports():
    import tkinter  # noqa: F401 - ensure stdlib GUI module exists

    mod = importlib.import_module("comms.gui_client")
    assert hasattr(mod, "StarbotGuiClient")
    assert hasattr(mod, "launch_gui")


def test_start_gui_parse_cli():
    mod = importlib.import_module("start_gui")
    assert mod._parse_cli(["setup"]) == {"force_setup": True, "setup_only": True}
    assert mod._parse_cli(["--setup-only"]) == {"force_setup": True, "setup_only": True}
    assert mod._parse_cli(["--setup"]) == {"force_setup": True, "setup_only": False}
    assert mod._parse_cli([]) == {"force_setup": False, "setup_only": False}

