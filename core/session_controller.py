from __future__ import annotations

import threading
import time
from queue import Empty, Queue
from typing import Any, Callable


Event = dict[str, Any]


def _default_brain_factory():
    # Lazy import to avoid importing heavy runtime deps during module import/tests.
    from core.brain import Brain

    return Brain()


class SessionController:
    """
    Threaded chat/session runner for local clients (GUI/CLI wrappers).

    Reuses the existing `Brain` + tool execution loop and emits queue-based events
    for UI layers. Core logic is unchanged; this is only an orchestration shell.
    """

    def __init__(
        self,
        *,
        brain_factory: Callable[[], Any] | None = None,
        max_steps: int = 30,
    ):
        self._brain_factory = brain_factory or _default_brain_factory
        self._max_steps = max_steps
        self._brain = None
        self._worker: threading.Thread | None = None
        self._cancel = threading.Event()
        self._events: Queue[Event] = Queue()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ state

    @property
    def is_busy(self) -> bool:
        t = self._worker
        return bool(t and t.is_alive())

    def has_session(self) -> bool:
        return self._brain is not None

    # ------------------------------------------------------------------ events

    def _emit(self, type_: str, **payload):
        self._events.put(
            {
                "type": type_,
                "time": time.time(),
                **payload,
            }
        )

    def drain_events(self, limit: int = 200) -> list[Event]:
        out: list[Event] = []
        for _ in range(max(1, limit)):
            try:
                out.append(self._events.get_nowait())
            except Empty:
                break
        return out

    # ------------------------------------------------------------------ session

    def reset_session(self) -> bool:
        with self._lock:
            if self.is_busy:
                return False
            self._brain = None
        self._emit("session_reset")
        self._emit("status", text="Session reset")
        return True

    def cancel(self):
        self._cancel.set()
        self._emit("status", text="Cancellation requested")

    def send_message(self, text: str) -> bool:
        message = (text or "").strip()
        if not message:
            return False
        with self._lock:
            if self.is_busy:
                return False
            self._cancel.clear()
            self._worker = threading.Thread(
                target=self._run_worker,
                args=(message,),
                daemon=True,
                name="starbot-session-worker",
            )
            self._worker.start()
        self._emit("status", text="Queued")
        return True

    # ------------------------------------------------------------------ worker

    def _ensure_brain(self):
        if self._brain is None:
            self._brain = self._brain_factory()
            self._emit("session_created")
        return self._brain

    def _emit_tool_calls_from_delta(self, before_count: int, after_count: int):
        if self._brain is None or after_count <= before_count:
            return
        try:
            new_msgs = self._brain.messages[before_count:after_count]
        except Exception:
            return
        for msg in new_msgs:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "assistant":
                continue
            tcalls = msg.get("tool_calls")
            if not isinstance(tcalls, list) or not tcalls:
                continue
            names: list[str] = []
            for tc in tcalls:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                if isinstance(fn, dict):
                    name = str(fn.get("name", "")).strip()
                    if name:
                        names.append(name)
            if names:
                self._emit("tool_call", names=names, count=len(names))

    def _run_worker(self, user_text: str):
        self._emit("busy", value=True)
        self._emit("user", text=user_text)
        try:
            brain = self._ensure_brain()
            brain._append_user(user_text)
            self._emit("status", text="Thinking...")

            for step_index in range(1, self._max_steps + 1):
                if self._cancel.is_set():
                    self._emit("cancelled")
                    self._emit("status", text="Cancelled")
                    break

                before_count = len(getattr(brain, "messages", []) or [])
                result = brain.step()
                after_count = len(getattr(brain, "messages", []) or [])
                self._emit_tool_calls_from_delta(before_count, after_count)

                if result is None:
                    self._emit("status", text="No response")
                    self._emit("done", reason="no_result")
                    break

                # Plain assistant text (no tool call)
                if isinstance(result, dict) and "text" in result and "name" not in result:
                    text = str(result.get("text", "") or "").strip()
                    if text:
                        self._emit("assistant", text=text, final=True)
                    self._emit("done", reason="assistant_text")
                    self._emit("status", text="Completed")
                    break

                # Tool-step result (Brain.step() executes the tool internally).
                if isinstance(result, dict):
                    summary = str(result.get("result", "") or "")
                    self._emit(
                        "tool_result",
                        ok=bool(result.get("ok", True)),
                        done=bool(result.get("done", False)),
                        summary=summary[:2000],
                        step=step_index,
                    )
                    if result.get("done"):
                        final_text = summary.strip()
                        if final_text:
                            self._emit("assistant", text=final_text, final=True)
                        self._emit("done", reason="done_tool")
                        self._emit("status", text="Completed")
                        break

                    self._emit("status", text=f"Running step {step_index}...")
                    continue

                # Defensive fallback for unexpected result types.
                self._emit("assistant", text=str(result), final=True)
                self._emit("done", reason="unexpected_result")
                self._emit("status", text="Completed")
                break
            else:
                self._emit("assistant", text="Max steps reached.", final=True)
                self._emit("done", reason="max_steps")
                self._emit("status", text="Max steps reached")

        except Exception as e:
            self._emit("error", message=str(e))
            self._emit("status", text="Error")
            self._emit("done", reason="error")
        finally:
            self._emit("busy", value=False)

