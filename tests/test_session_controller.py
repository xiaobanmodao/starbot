from __future__ import annotations

import time

from core.session_controller import SessionController


class FakeBrain:
    def __init__(self, scripted_results=None, step_delay: float = 0.0):
        self.messages: list[dict] = [{"role": "system", "content": "x"}]
        self._results = list(scripted_results or [])
        self._step_delay = step_delay

    def _append_user(self, text: str, image_path: str | None = None):
        self.messages.append({"role": "user", "content": text})

    def step(self):
        if self._step_delay:
            time.sleep(self._step_delay)
        if not self._results:
            return None
        item = self._results.pop(0)
        if isinstance(item, tuple) and item and item[0] == "tool":
            _, names, result = item
            self.messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {"id": f"t{i}", "type": "function", "function": {"name": n, "arguments": "{}"}}
                        for i, n in enumerate(names)
                    ],
                }
            )
            self.messages.append({"role": "tool", "tool_call_id": "t0", "content": "{}"})
            return result
        if isinstance(item, dict):
            self.messages.append({"role": "assistant", "content": item.get("text", item.get("result", ""))})
            return item
        return item


def _drain_until_idle(ctrl: SessionController, timeout: float = 2.0):
    deadline = time.time() + timeout
    events = []
    while time.time() < deadline:
        events.extend(ctrl.drain_events())
        if not ctrl.is_busy:
            time.sleep(0.02)
            events.extend(ctrl.drain_events())
            return events
        time.sleep(0.02)
    raise AssertionError("controller did not become idle in time")


def test_session_controller_emits_assistant_text_and_done():
    ctrl = SessionController(
        brain_factory=lambda: FakeBrain([{"text": "hello from assistant"}]),
        max_steps=5,
    )
    assert ctrl.send_message("hi") is True
    events = _drain_until_idle(ctrl)

    types = [e["type"] for e in events]
    assert "user" in types
    assert "assistant" in types
    assert "done" in types
    assert "busy" in types
    assistant_events = [e for e in events if e["type"] == "assistant"]
    assert assistant_events[-1]["text"] == "hello from assistant"


def test_session_controller_emits_tool_calls_and_final_done_tool_text():
    ctrl = SessionController(
        brain_factory=lambda: FakeBrain(
            [
                ("tool", ["web_search", "fetch_page"], {"ok": True, "result": "tool interim"}),
                ("tool", ["done"], {"ok": True, "done": True, "result": "final summary"}),
            ]
        ),
        max_steps=5,
    )
    assert ctrl.send_message("research this") is True
    events = _drain_until_idle(ctrl)

    tool_call_events = [e for e in events if e["type"] == "tool_call"]
    assert tool_call_events
    assert tool_call_events[0]["names"] == ["web_search", "fetch_page"]

    tool_result_events = [e for e in events if e["type"] == "tool_result"]
    assert len(tool_result_events) >= 2
    assert any(e.get("done") for e in tool_result_events)

    assistant_texts = [e["text"] for e in events if e["type"] == "assistant"]
    assert "final summary" in assistant_texts


def test_session_controller_cancel_stops_between_steps():
    ctrl = SessionController(
        brain_factory=lambda: FakeBrain(
            [
                ("tool", ["web_search"], {"ok": True, "result": "step1"}),
                ("tool", ["fetch_page"], {"ok": True, "result": "step2"}),
            ],
            step_delay=0.15,
        ),
        max_steps=5,
    )
    assert ctrl.send_message("long task") is True
    time.sleep(0.05)
    ctrl.cancel()
    events = _drain_until_idle(ctrl, timeout=3.0)

    types = [e["type"] for e in events]
    assert "cancelled" in types or any(
        e["type"] == "status" and "Cancel" in str(e.get("text", "")) for e in events
    )


def test_session_controller_reset_reuses_rules():
    created = {"count": 0}

    def make_brain():
        created["count"] += 1
        return FakeBrain([{"text": "ok"}])

    ctrl = SessionController(brain_factory=make_brain)
    assert ctrl.reset_session() is True  # no session yet is fine
    assert ctrl.send_message("a") is True
    _drain_until_idle(ctrl)
    assert created["count"] == 1
    assert ctrl.has_session() is True

    assert ctrl.reset_session() is True
    assert ctrl.has_session() is False
    assert ctrl.send_message("b") is True
    _drain_until_idle(ctrl)
    assert created["count"] == 2

