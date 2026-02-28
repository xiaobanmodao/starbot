from __future__ import annotations

import base64
import json
import mimetypes
import threading
import time
import uuid
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable


Event = dict[str, Any]

_BASE_DIR = Path(__file__).resolve().parent.parent
_SESSIONS_FILE = _BASE_DIR / "logs" / "local_sessions.json"


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
        # Confirmation gate for dangerous tools
        self._confirm_event = threading.Event()
        self._confirm_result: bool = False

        # Multi-session state
        self._sessions: dict[str, dict[str, Any]] = {}
        self._current_session_id: str | None = None
        self._load_sessions()
        if self._current_session_id is None:
            self.create_session(title="新会话")

    # ------------------------------------------------------------------ state

    @property
    def is_busy(self) -> bool:
        t = self._worker
        return bool(t and t.is_alive())

    def has_session(self) -> bool:
        return self._brain is not None

    def usage_snapshot(self) -> dict[str, Any]:
        brain = self._brain
        if brain is None:
            return {"input": 0, "output": 0, "calls": 0}
        usage = getattr(brain, "usage", None)
        if isinstance(usage, dict):
            return {
                "input": int(usage.get("input", 0) or 0),
                "output": int(usage.get("output", 0) or 0),
                "calls": int(usage.get("calls", 0) or 0),
            }
        return {"input": 0, "output": 0, "calls": 0}

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

    # ------------------------------------------------------------------ persistence

    def _message_to_text(self, msg: dict) -> str:
        c = msg.get("content", "")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts: list[str] = []
            has_image = False
            for p in c:
                if not isinstance(p, dict):
                    continue
                ptype = p.get("type")
                if ptype == "text":
                    parts.append(str(p.get("text", "")))
                elif ptype == "image_url":
                    has_image = True
            text = "\n".join(x for x in parts if x).strip()
            if text:
                return text
            return "[image omitted]" if has_image else ""
        return ""

    def _serialize_messages(self, messages: list[dict]) -> list[dict]:
        out: list[dict] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in {"system", "user", "assistant", "tool"}:
                continue
            item: dict[str, Any] = {"role": role}
            if role in {"user", "assistant"}:
                item["content"] = self._message_to_text(msg)
            elif role == "system":
                item["content"] = self._message_to_text(msg)
            else:
                item["content"] = str(msg.get("content", ""))[:2000]
            if msg.get("tool_call_id"):
                item["tool_call_id"] = msg.get("tool_call_id")
            out.append(item)
        return out

    def _persist_sessions(self):
        try:
            _SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "current_session_id": self._current_session_id,
                "sessions": {},
            }
            for sid, meta in self._sessions.items():
                payload["sessions"][sid] = {
                    "id": sid,
                    "title": meta.get("title") or "新会话",
                    "created_at": float(meta.get("created_at") or time.time()),
                    "updated_at": float(meta.get("updated_at") or time.time()),
                    "messages": self._serialize_messages(meta.get("brain").messages if meta.get("brain") else []),
                }
            _SESSIONS_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _load_sessions(self):
        try:
            if not _SESSIONS_FILE.exists():
                return
            data = json.loads(_SESSIONS_FILE.read_text(encoding="utf-8"))
            sessions = data.get("sessions") or {}
            for sid, item in sessions.items():
                brain = self._brain_factory()
                msgs = item.get("messages") if isinstance(item, dict) else []
                if isinstance(msgs, list) and msgs:
                    sys_msg = brain.messages[0] if brain.messages else {"role": "system", "content": ""}
                    restored = [sys_msg]
                    for m in msgs:
                        if not isinstance(m, dict):
                            continue
                        role = m.get("role")
                        if role == "system":
                            continue
                        if role not in {"user", "assistant", "tool"}:
                            continue
                        restored.append({
                            "role": role,
                            "content": str(m.get("content", "")),
                            **({"tool_call_id": m.get("tool_call_id")} if m.get("tool_call_id") else {}),
                        })
                    brain.messages = restored
                self._sessions[sid] = {
                    "id": sid,
                    "title": item.get("title") or "新会话",
                    "created_at": float(item.get("created_at") or time.time()),
                    "updated_at": float(item.get("updated_at") or time.time()),
                    "brain": brain,
                }
            current = str(data.get("current_session_id") or "")
            if current and current in self._sessions:
                self._current_session_id = current
                self._brain = self._sessions[current].get("brain")
            elif self._sessions:
                first = next(iter(self._sessions.keys()))
                self._current_session_id = first
                self._brain = self._sessions[first].get("brain")
        except Exception:
            self._sessions = {}
            self._current_session_id = None
            self._brain = None

    # ------------------------------------------------------------------ session list/switch

    def _session_title_from_brain(self, brain: Any, fallback: str = "新会话") -> str:
        try:
            for msg in getattr(brain, "messages", [])[1:]:
                if isinstance(msg, dict) and msg.get("role") == "user":
                    text = self._message_to_text(msg).strip()
                    if text:
                        return text[:28]
        except Exception:
            pass
        return fallback

    def _current_meta(self) -> dict[str, Any] | None:
        sid = self._current_session_id
        if not sid:
            return None
        return self._sessions.get(sid)

    def list_sessions(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for sid, meta in self._sessions.items():
            items.append({
                "id": sid,
                "title": str(meta.get("title") or "新会话"),
                "created_at": float(meta.get("created_at") or 0),
                "updated_at": float(meta.get("updated_at") or 0),
                "is_current": sid == self._current_session_id,
            })
        items.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return items

    def create_session(self, title: str = "") -> str:
        sid = uuid.uuid4().hex[:12]
        brain = self._brain_factory()
        now = time.time()
        self._sessions[sid] = {
            "id": sid,
            "title": (title or "新会话").strip()[:50] or "新会话",
            "created_at": now,
            "updated_at": now,
            "brain": brain,
        }
        self._current_session_id = sid
        self._brain = brain
        self._persist_sessions()
        self._emit("session_switched", session_id=sid, title=self._sessions[sid]["title"])
        return sid

    def switch_session(self, session_id: str) -> bool:
        sid = (session_id or "").strip()
        if not sid or sid not in self._sessions:
            return False
        if self.is_busy:
            return False
        self._current_session_id = sid
        self._brain = self._sessions[sid].get("brain")
        # Note: Don't update updated_at here - only update on actual message interaction
        self._persist_sessions()
        self._emit("session_switched", session_id=sid, title=self._sessions[sid].get("title", "新会话"))
        return True

    def get_current_session(self) -> dict[str, Any]:
        meta = self._current_meta() or {}
        return {
            "id": self._current_session_id,
            "title": str(meta.get("title") or "新会话"),
        }

    def rename_session(self, session_id: str, title: str) -> bool:
        sid = (session_id or "").strip()
        if not sid or sid not in self._sessions:
            return False
        new_title = (title or "").strip()[:50] or "新会话"
        self._sessions[sid]["title"] = new_title
        self._sessions[sid]["updated_at"] = time.time()
        self._persist_sessions()
        return True

    def delete_session(self, session_id: str) -> bool:
        sid = (session_id or "").strip()
        if not sid or sid not in self._sessions:
            return False
        if self.is_busy and sid == self._current_session_id:
            return False

        self._sessions.pop(sid, None)
        if not self._sessions:
            self.create_session(title="新会话")
            return True

        if sid == self._current_session_id:
            next_id = next(iter(self._sessions.keys()))
            self._current_session_id = next_id
            self._brain = self._sessions[next_id].get("brain")
            self._emit("session_switched", session_id=next_id, title=self._sessions[next_id].get("title", "新会话"))
        self._persist_sessions()
        return True

    def get_current_transcript(self) -> list[dict[str, str]]:
        brain = self._brain
        if brain is None:
            return []
        out: list[dict[str, str]] = []
        for msg in getattr(brain, "messages", []):
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role not in {"user", "assistant"}:
                continue
            text = self._message_to_text(msg).strip()
            if not text:
                continue
            out.append({"role": role, "text": text})
        return out

    # ------------------------------------------------------------------ session actions

    def reset_session(self) -> bool:
        with self._lock:
            if self.is_busy:
                return False
            if not self._current_session_id or self._current_session_id not in self._sessions:
                self.create_session(title="新会话")
                return True
            brain = self._brain_factory()
            self._sessions[self._current_session_id]["brain"] = brain
            self._sessions[self._current_session_id]["updated_at"] = time.time()
            self._sessions[self._current_session_id]["title"] = "新会话"
            self._brain = brain
            self._persist_sessions()
        self._emit("session_reset")
        self._emit("status", text="Session reset")
        return True

    def cancel(self):
        self._cancel.set()
        # Unblock any pending confirmation wait
        self._confirm_result = False
        self._confirm_event.set()
        self._emit("status", text="Cancellation requested")

    def confirm_response(self, approved: bool):
        """Called by the UI layer when user approves/denies a dangerous tool."""
        self._confirm_result = approved
        self._confirm_event.set()

    def send_message(self, text: str, attachments: list[dict] | None = None) -> bool:
        message = (text or "").strip()
        if not message and not attachments:
            return False
        with self._lock:
            if self.is_busy:
                return False
            self._cancel.clear()
            self._worker = threading.Thread(
                target=self._run_worker,
                args=(message, attachments),
                daemon=True,
                name="starbot-session-worker",
            )
            self._worker.start()
        self._emit("status", text="Queued")
        return True

    # ------------------------------------------------------------------ worker

    def _ensure_brain(self):
        if self._brain is None:
            sid = self._current_session_id
            if sid and sid in self._sessions and self._sessions[sid].get("brain") is not None:
                self._brain = self._sessions[sid]["brain"]
            else:
                self._brain = self._brain_factory()
                new_id = sid or uuid.uuid4().hex[:12]
                now = time.time()
                self._sessions[new_id] = {
                    "id": new_id,
                    "title": "新会话",
                    "created_at": now,
                    "updated_at": now,
                    "brain": self._brain,
                }
                self._current_session_id = new_id
            self._brain._confirm_callback = self._confirm_tool
            self._emit("session_created")
        return self._brain

    def _confirm_tool(self, tool_name: str, tool_args: dict) -> bool:
        """Block worker thread until user approves or denies the tool call."""
        self._confirm_event.clear()
        self._confirm_result = False
        self._emit("confirm_request", tool=tool_name, args=tool_args)
        # Wait up to 120s for user response
        self._confirm_event.wait(timeout=120)
        if not self._confirm_event.is_set():
            # Timeout — treat as denied
            self._emit("status", text="Confirmation timed out")
            return False
        return self._confirm_result

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

    def _encode_image_payload(self, image_path: str) -> dict[str, str] | None:
        """Encode an image file to a compact event payload for UI rendering."""
        p = Path(str(image_path or "")).expanduser()
        if not p.is_absolute():
            p = Path.cwd() / p
        try:
            if not p.exists() or not p.is_file():
                return None
            raw = p.read_bytes()
            if not raw:
                return None
            mime, _ = mimetypes.guess_type(str(p))
            if not mime or not mime.startswith("image/"):
                mime = "image/jpeg"
            return {
                "mime": mime,
                "base64": base64.b64encode(raw).decode("ascii"),
                "name": p.name,
            }
        except Exception:
            return None

    def _touch_current_session(self):
        sid = self._current_session_id
        if not sid or sid not in self._sessions:
            return
        meta = self._sessions[sid]
        meta["updated_at"] = time.time()
        brain = meta.get("brain")
        if brain is not None:
            meta["title"] = self._session_title_from_brain(brain, fallback=str(meta.get("title") or "新会话"))

    def _run_worker(self, user_text: str, attachments: list[dict] | None = None):
        self._emit("busy", value=True)
        self._emit("user", text=user_text)
        try:
            brain = self._ensure_brain()
            try:
                brain._append_user(user_text, attachments=attachments)
            except TypeError:
                # Backward compatibility for tests/fakes that still expose
                # _append_user(text, image_path=None).
                brain._append_user(user_text)
            self._touch_current_session()
            self._persist_sessions()
            self._emit("status", text="Thinking...")

            _stream_started = False

            _reasoning_buffer = ""
            _in_reasoning = False
            
            def _on_chunk(delta: str):
                nonlocal _stream_started, _reasoning_buffer, _in_reasoning
                # Filter out reasoning tags and their content
                if not delta or not isinstance(delta, str):
                    return
                
                # Handle reasoning tags (including redacted_reasoning and think tags)
                delta_lower = delta.lower()
                reasoning_tags = ["<reasoning>", "<think>", "<think>"]
                closing_tags = ["</reasoning>", "</think>", "</think>"]
                
                # Check for opening tags
                if any(tag in delta_lower for tag in reasoning_tags):
                    _in_reasoning = True
                    _reasoning_buffer = ""
                    return
                
                # Check for closing tags
                if any(tag in delta_lower for tag in closing_tags):
                    _in_reasoning = False
                    _reasoning_buffer = ""
                    return
                
                # Skip content inside reasoning tags
                if _in_reasoning:
                    _reasoning_buffer += delta
                    return
                
                # Skip if delta contains reasoning-like patterns (partial tags)
                if any(tag in delta_lower for tag in reasoning_tags + closing_tags):
                    return
                
                if not _stream_started:
                    _stream_started = True
                    self._emit("stream_start")
                self._emit("stream_delta", text=delta)

            def _on_clear():
                nonlocal _stream_started
                if _stream_started:
                    self._emit("stream_clear")
                    _stream_started = False

            for step_index in range(1, self._max_steps + 1):
                if self._cancel.is_set():
                    self._emit("cancelled")
                    self._emit("done", reason="cancelled")
                    self._emit("status", text="Cancelled")
                    break

                _stream_started = False

                before_count = len(getattr(brain, "messages", []) or [])
                if hasattr(brain, "step_stream"):
                    result = brain.step_stream(
                        on_chunk=_on_chunk,
                        on_clear=_on_clear,
                        cancel_check=self._cancel.is_set,
                    )
                else:
                    # Backward compatibility: some tests/fakes only implement step().
                    result = brain.step()
                after_count = len(getattr(brain, "messages", []) or [])
                self._emit_tool_calls_from_delta(before_count, after_count)

                if _stream_started:
                    self._emit("stream_end")
                    _stream_started = False

                # Check cancel again after step completes
                if self._cancel.is_set():
                    self._emit("cancelled")
                    self._emit("done", reason="cancelled")
                    self._emit("status", text="Cancelled")
                    break

                if result is None:
                    if self._cancel.is_set():
                        self._emit("cancelled")
                        self._emit("done", reason="cancelled")
                        self._emit("status", text="Cancelled")
                    else:
                        self._emit("status", text="No response")
                        self._emit("done", reason="no_result")
                    break

                # Plain assistant text (no tool call)
                if isinstance(result, dict) and "text" in result and "name" not in result:
                    text = str(result.get("text", "") or "").strip()
                    if text and not result.get("streamed"):
                        # Not streamed — emit full text at once
                        self._emit("assistant", text=text, final=True)
                    # If streamed, the text was already delivered via stream_delta events
                    self._emit("done", reason="assistant_text")
                    self._emit("status", text="Completed")
                    break

                # Tool-step result (Brain.step() executes the tool internally).
                if isinstance(result, dict):
                    summary = str(result.get("result", "") or "")
                    image_payload = None
                    image_path = result.get("image")
                    if image_path:
                        image_payload = self._encode_image_payload(str(image_path))
                    self._emit(
                        "tool_result",
                        ok=bool(result.get("ok", True)),
                        done=bool(result.get("done", False)),
                        summary=summary[:2000],
                        step=step_index,
                        image=image_payload,
                    )
                    if result.get("done"):
                        if summary:
                            self._emit("assistant", text=summary, final=True)
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
            self._touch_current_session()
            self._persist_sessions()
            self._emit("busy", value=False)
