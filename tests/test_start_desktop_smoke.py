from __future__ import annotations

import importlib


class _FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


def test_start_desktop_parse_cli():
    mod = importlib.import_module("start_desktop")
    parsed = mod._parse_cli(
        [
            "--setup",
            "--host",
            "0.0.0.0",
            "--port",
            "9999",
            "--width",
            "1600",
            "--height",
            "900",
            "--maximized",
            "--debug-webview",
        ]
    )
    assert parsed["force_setup"] is True
    assert parsed["setup_only"] is False
    assert parsed["host"] == "0.0.0.0"
    assert parsed["port"] == 9999
    assert parsed["width"] == 1600
    assert parsed["height"] == 900
    assert parsed["maximized"] is True
    assert parsed["debug_webview"] is True


def test_start_desktop_ensure_pywebview_dep_uses_pip_fallback():
    mod = importlib.import_module("start_desktop")

    class FakeStart:
        def __init__(self):
            self.installs = []

        def _can_import(self, name: str):
            assert name == "webview"
            return False

        def _pip_install(self, packages):
            self.installs.append(list(packages))
            return True

    fake = FakeStart()
    ok = mod._ensure_desktop_webview_dep(fake)
    assert ok is True
    assert fake.installs == [["pywebview>=5.4"]]


def test_start_desktop_attach_close_handler_best_effort():
    mod = importlib.import_module("start_desktop")
    called = {"n": 0}

    def on_close():
        called["n"] += 1

    events = type("Events", (), {"closed": _FakeEvent()})()
    window = type("Window", (), {"events": events})()

    mod._attach_close_handler(window, on_close)
    assert len(events.closed.handlers) == 1
    events.closed.handlers[0]()
    assert called["n"] == 1
