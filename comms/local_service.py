from __future__ import annotations

import base64
import io
import importlib.util
import os
import shlex
import shutil
import time
from pathlib import Path
from typing import Any

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None

from core.session_controller import SessionController


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


class LocalClientService:
    """
    Local UI service/router.

    Purpose:
    - Reuse existing Starbot core (Brain/tools/memory/skills/config)
    - Provide a GUI/web-friendly structured API
    - Preserve Discord flow (this does not replace or modify discord_client)
    """

    CONFIG_KEYS = [
        "LLM_API_BASE",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM2_API_BASE",
        "LLM2_API_KEY",
        "LLM2_MODEL",
        "DISCORD_BOT_TOKEN",
        "DISCORD_OWNER_ID",
        "DISCORD_CHANNEL_ID",
        "DISCORD_PROXY",
    ]

    def __init__(
        self,
        *,
        controller: SessionController | None = None,
        memory=None,
        skill_manager=None,
        task_mgr=None,
        config_obj=None,
        config_module=None,
        llm_client=None,
        screenshot_provider=None,
    ):
        # Lazily import heavy/runtime modules only when no DI override is provided.
        if controller is None:
            controller = SessionController()
        self.controller = controller

        if memory is None:
            from memory.store import MemoryStore

            memory = MemoryStore()
        self.memory = memory

        if skill_manager is None or task_mgr is None or screenshot_provider is None:
            from actions.executor import _skill_manager, _task_mgr

            if skill_manager is None:
                skill_manager = _skill_manager
            if task_mgr is None:
                task_mgr = _task_mgr
            if screenshot_provider is None:
                screenshot_provider = self._default_screenshot_provider
        self.skill_manager = skill_manager
        self.task_mgr = task_mgr
        self._screenshot_provider = screenshot_provider

        if config_obj is None or config_module is None:
            import config as _config_module
            from config import config as _config_obj

            if config_module is None:
                config_module = _config_module
            if config_obj is None:
                config_obj = _config_obj
        self.config = config_obj
        self._config_module = config_module

        self._llm_client = llm_client  # Optional override for tests

    # ------------------------------------------------------------------ helpers

    def _result(self, ok: bool = True, *, message: str = "", data: Any = None, code: str = "") -> dict:
        return {"ok": ok, "message": message, "data": data, "code": code}

    @staticmethod
    def _default_screenshot_provider() -> tuple[bool, str, str | None]:
        try:
            import pyautogui
            from PIL import Image
        except Exception as e:
            return False, f"screenshot dependencies unavailable: {e}", None
        try:
            img = pyautogui.screenshot()
            if not isinstance(img, Image.Image):
                return False, "screenshot provider returned unexpected object", None
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=75)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return True, "ok", b64
        except Exception as e:
            return False, str(e), None

    def _set_config_value(self, key: str, value: str):
        key = key.strip()
        value = value if value is not None else ""

        if key == "LLM_MODEL":
            # Existing project treats LLM_MODEL as runtime stateful selection.
            self._config_module._save_state({"LLM_MODEL": value})
            setattr(self.config, "LLM_MODEL", value)
            os.environ["LLM_MODEL"] = value
            return

        self._config_module._write_env(key, value)
        os.environ[key] = value

        # Keep singleton config object in sync.
        if key == "DISCORD_CHANNEL_ID":
            try:
                setattr(self.config, key, int(value or "0"))
            except Exception:
                setattr(self.config, key, 0)
        else:
            setattr(self.config, key, value)

    def _config_snapshot(self, *, masked: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in self.CONFIG_KEYS:
            try:
                val = getattr(self.config, key)
            except Exception:
                val = os.environ.get(key, "")
            if key in {"DISCORD_CHANNEL_ID"} and isinstance(val, int):
                raw = str(val or "")
            else:
                raw = str(val or "")
            if masked and key in {"LLM_API_KEY", "LLM2_API_KEY", "DISCORD_BOT_TOKEN"}:
                out[key] = _mask_secret(raw)
            else:
                out[key] = raw
        return out

    def _llm(self):
        if self._llm_client is not None:
            return self._llm_client
        from core.adapter import UniversalLLM

        return UniversalLLM(self.config.LLM_API_KEY, self.config.LLM_API_BASE, self.config.LLM_MODEL)

    # ------------------------------------------------------------------ chat/session

    def send_chat(self, text: str, *, attachments: list[dict] | None = None) -> dict:
        if self.controller.is_busy:
            return self._result(False, message="Session is busy. Stop current task first.", code="busy")
        if not self.controller.send_message(text, attachments=attachments):
            return self._result(False, message="Empty message or failed to queue.", code="send_failed")
        return self._result(True, message="Queued", data={"queued": True})

    def poll_chat_events(self, limit: int = 200) -> dict:
        events = self.controller.drain_events(limit=limit)
        return self._result(
            True,
            data={
                "events": events,
                "busy": self.controller.is_busy,
                "has_session": self.controller.has_session(),
                "usage": self.controller.usage_snapshot() if hasattr(self.controller, "usage_snapshot") else {},
            },
        )

    def stop_chat(self) -> dict:
        self.controller.cancel()
        return self._result(True, message="Cancellation requested")

    def reset_chat(self) -> dict:
        ok = self.controller.reset_session()
        if not ok:
            return self._result(False, message="Cannot reset while session is busy", code="busy")
        return self._result(True, message="Session reset")

    def chat_usage(self) -> dict:
        usage = self.controller.usage_snapshot() if hasattr(self.controller, "usage_snapshot") else {}
        return self._result(True, data=usage)

    # ------------------------------------------------------------------ status/doctor

    def status(self) -> dict:
        cpu = None
        mem = None
        try:
            if psutil is None:
                raise RuntimeError("psutil unavailable")
            cpu = psutil.cpu_percent(interval=0.1)
            vmem = psutil.virtual_memory()
            mem = {
                "percent": vmem.percent,
                "used": int(vmem.used),
                "total": int(vmem.total),
            }
        except Exception:
            pass

        tasks = []
        try:
            for t in getattr(self.task_mgr, "list_all", lambda: [])():
                tasks.append(
                    {
                        "id": getattr(t, "id", 0),
                        "name": getattr(t, "name", ""),
                        "status": getattr(t, "status", ""),
                        "steps": getattr(t, "steps", 0),
                        "result": getattr(t, "result", ""),
                        "created_at": getattr(t, "created_at", 0.0),
                    }
                )
        except Exception:
            pass

        usage = self.controller.usage_snapshot() if hasattr(self.controller, "usage_snapshot") else {}
        return self._result(
            True,
            data={
                "cpu": cpu,
                "memory": mem,
                "tasks": tasks,
                "tasks_summary": getattr(self.task_mgr, "summary", lambda: "")(),
                "session_busy": self.controller.is_busy,
                "session_active": self.controller.has_session(),
                "usage": usage,
                "model": str(getattr(self.config, "LLM_MODEL", "")),
            },
        )

    def doctor(self) -> dict:
        cfg = self._config_snapshot(masked=True)
        cfg_ok = {
            "LLM_API_BASE": bool(str(cfg.get("LLM_API_BASE", "")).strip()),
            "LLM_API_KEY": bool(str(getattr(self.config, "LLM_API_KEY", "")).strip()),
            "DISCORD_BOT_TOKEN": bool(str(getattr(self.config, "DISCORD_BOT_TOKEN", "")).strip()),
            "DISCORD_OWNER_ID": bool(str(getattr(self.config, "DISCORD_OWNER_ID", "")).strip()),
            "DISCORD_CHANNEL_ID": bool(int(getattr(self.config, "DISCORD_CHANNEL_ID", 0) or 0)),
        }

        def _has_mod(name: str) -> bool:
            try:
                return importlib.util.find_spec(name) is not None
            except Exception:
                return False

        checks = [
            {
                "id": "playwright",
                "label": "Playwright",
                "ok": _has_mod("playwright"),
                "kind": "python",
                "hint": "pip install playwright && playwright install chromium",
            },
            {
                "id": "pytesseract",
                "label": "pytesseract",
                "ok": _has_mod("pytesseract"),
                "kind": "python",
                "hint": "pip install pytesseract",
            },
            {
                "id": "tesseract_bin",
                "label": "Tesseract OCR binary",
                "ok": bool(shutil.which("tesseract")),
                "kind": "binary",
                "hint": "Install Tesseract OCR and add it to PATH",
            },
            {
                "id": "yt_dlp",
                "label": "yt-dlp",
                "ok": bool(shutil.which("yt-dlp") or _has_mod("yt_dlp")),
                "kind": "binary/python",
                "hint": "pip install yt-dlp",
            },
            {
                "id": "faster_whisper",
                "label": "faster-whisper",
                "ok": _has_mod("faster_whisper"),
                "kind": "python",
                "hint": "pip install faster-whisper",
            },
            {
                "id": "trafilatura",
                "label": "trafilatura",
                "ok": _has_mod("trafilatura"),
                "kind": "python",
                "hint": "pip install trafilatura",
            },
        ]

        skill_count = 0
        try:
            skill_count = len(self.skill_manager.list_skills())
        except Exception:
            pass

        from memory.store import DB_PATH as MEMORY_DB_PATH

        features = {
            "ocr": _has_mod("pytesseract") and bool(shutil.which("tesseract")),
            "browser_agent": _has_mod("playwright"),
            "video_download_or_subtitles": bool(shutil.which("yt-dlp") or _has_mod("yt_dlp")),
            "whisper_transcription": _has_mod("faster_whisper"),
        }

        return self._result(
            True,
            data={
                "config": cfg,
                "config_ok": cfg_ok,
                "checks": checks,
                "features": features,
                "runtime": {
                    "skills_count": skill_count,
                    "tasks_summary": getattr(self.task_mgr, "summary", lambda: "")(),
                    "session_active": self.controller.has_session(),
                    "session_busy": self.controller.is_busy,
                    "memory_db": MEMORY_DB_PATH,
                    "memory_db_exists": Path(MEMORY_DB_PATH).exists(),
                    "model": str(getattr(self.config, "LLM_MODEL", "")),
                },
            },
        )

    # ------------------------------------------------------------------ screenshot

    def screenshot(self) -> dict:
        ok, msg, b64 = self._screenshot_provider()
        if not ok:
            return self._result(False, message=msg, code="screenshot_failed")
        return self._result(True, data={"jpeg_base64": b64})

    # ------------------------------------------------------------------ model/config

    def model_list(self) -> dict:
        try:
            llm = self._llm()
            resp = llm.client.with_options(timeout=8).models.list()
            models = [m.id for m in getattr(resp, "data", [])]
            return self._result(True, data={"models": models, "current": getattr(self.config, "LLM_MODEL", "")})
        except Exception as e:
            return self._result(False, message=str(e), code="model_list_failed")

    def model_set(self, name: str) -> dict:
        model = (name or "").strip()
        if not model:
            return self._result(False, message="Model name is required", code="invalid")
        self._set_config_value("LLM_MODEL", model)
        # Update running Brain's LLM model so the switch takes effect immediately
        if self.controller.has_session():
            brain = getattr(self.controller, "_brain", None)
            if brain and hasattr(brain, "llm"):
                brain.llm.model = model
        return self._result(True, message=f"Model switched to {model}", data={"current": model})

    def config_get(self) -> dict:
        return self._result(True, data={"config": self._config_snapshot(masked=True)})

    def config_set(self, key: str, value: str) -> dict:
        key = (key or "").strip()
        if key not in self.CONFIG_KEYS:
            return self._result(False, message=f"Unknown/unsupported config key: {key}", code="invalid_key")
        self._set_config_value(key, value)
        return self._result(True, message=f"Updated {key}", data={"config": self._config_snapshot(masked=True)})

    def config_update_many(self, values: dict[str, Any]) -> dict:
        updated: list[str] = []
        for key, value in (values or {}).items():
            if key not in self.CONFIG_KEYS:
                continue
            self._set_config_value(key, "" if value is None else str(value))
            updated.append(key)
        return self._result(True, message=f"Updated {len(updated)} items", data={"updated": updated, "config": self._config_snapshot(masked=True)})

    # ------------------------------------------------------------------ memory

    def memory_list(self, category: str = "", limit: int = 20) -> dict:
        rows = self.memory.list_by_category(category, limit=max(1, min(int(limit), 200)))
        return self._result(True, data={"items": rows})

    def memory_search(self, query: str, limit: int = 12) -> dict:
        q = (query or "").strip()
        if not q:
            return self._result(False, message="query is required", code="invalid")
        rows = self.memory.search_multi(q, limit=max(1, min(int(limit), 50)))
        return self._result(True, data={"items": rows})

    def memory_delete(self, memory_id: int) -> dict:
        ok = self.memory.delete_by_id(int(memory_id))
        return self._result(ok, message=("Deleted" if ok else "Delete failed"))

    def memory_stats(self) -> dict:
        return self._result(True, data={"stats": self.memory.stats()})

    # ------------------------------------------------------------------ skills

    def skills_list(self) -> dict:
        return self._result(True, data={"items": self.skill_manager.list_skills()})

    def skill_reload(self) -> dict:
        self.skill_manager.reload()
        return self._result(True, message="Skills reloaded", data={"items": self.skill_manager.list_skills()})

    def skill_install(self, source: str) -> dict:
        ok, msg = self.skill_manager.install(source)
        return self._result(ok, message=msg)

    def skill_remove(self, name: str) -> dict:
        ok, msg = self.skill_manager.remove(name)
        return self._result(ok, message=msg)

    def skill_info(self, name: str) -> dict:
        info = self.skill_manager.get_skill_info(name)
        if not info:
            return self._result(False, message=f"Skill not found: {name}", code="not_found")
        return self._result(True, data=info)

    def skill_update(self, name: str) -> dict:
        ok, msg = self.skill_manager.update(name)
        return self._result(ok, message=msg)

    # ------------------------------------------------------------------ tasks/rollback

    def tasks(self) -> dict:
        items = []
        for t in getattr(self.task_mgr, "list_all", lambda: [])():
            items.append(
                {
                    "id": getattr(t, "id", 0),
                    "name": getattr(t, "name", ""),
                    "status": getattr(t, "status", ""),
                    "result": getattr(t, "result", ""),
                    "steps": getattr(t, "steps", 0),
                    "created_at": getattr(t, "created_at", 0.0),
                }
            )
        return self._result(True, data={"items": items, "summary": getattr(self.task_mgr, "summary", lambda: "")()})

    def rollback(self, n: int = 1) -> dict:
        from core.op_log import undo_last

        msgs = undo_last(max(1, min(int(n), 10)))
        return self._result(True, data={"messages": msgs}, message="\n".join(msgs))

    # ------------------------------------------------------------------ command router (Discord-style parity)

    def help_info(self) -> dict:
        commands = [
            "/help",
            "/status",
            "/doctor",
            "/stop",
            "/screenshot",
            "/model [name]",
            "/skill [list|install|info|update|remove|reload] ...",
            "/memory [list|search|delete|stats] ...",
            "/config [key] [value]",
            "/reset",
            "/usage",
            "/tasks",
            "/rollback [n]",
        ]
        return self._result(True, data={"commands": commands})

    def exec_command(self, text: str) -> dict:
        raw = (text or "").strip()
        if not raw:
            return self._result(False, message="Empty command", code="invalid")

        # Non-command text => chat
        if not raw.startswith("/"):
            return self.send_chat(raw)

        if raw in {"/help"}:
            return self.help_info()
        if raw in {"/status"}:
            return self.status()
        if raw in {"/doctor"}:
            return self.doctor()
        if raw in {"/stop"}:
            return self.stop_chat()
        if raw in {"/screenshot"}:
            return self.screenshot()
        if raw in {"/reset"}:
            return self.reset_chat()
        if raw in {"/usage"}:
            return self.chat_usage()
        if raw in {"/tasks"}:
            return self.tasks()

        if raw.startswith("/rollback"):
            parts = raw.split(maxsplit=1)
            n = 1
            if len(parts) == 2:
                try:
                    n = int(parts[1].strip())
                except Exception:
                    return self._result(False, message="Usage: /rollback [n]", code="invalid")
            return self.rollback(n)

        if raw.startswith("/model"):
            parts = raw.split(maxsplit=1)
            if len(parts) == 1:
                return self.model_list()
            return self.model_set(parts[1].strip())

        if raw.startswith("/config"):
            parts = raw.split(maxsplit=2)
            if len(parts) == 1:
                return self.config_get()
            if len(parts) == 2:
                key = parts[1].strip()
                cfg = self._config_snapshot(masked=True)
                if key not in cfg:
                    return self._result(False, message=f"Unknown config key: {key}", code="invalid_key")
                return self._result(True, data={key: cfg[key]})
            return self.config_set(parts[1].strip(), parts[2])

        if raw.startswith("/memory"):
            parts = raw.split(maxsplit=2)
            sub = parts[1].lower() if len(parts) > 1 else "list"
            arg = parts[2] if len(parts) > 2 else ""
            if sub == "list":
                return self.memory_list(category=arg.strip(), limit=20)
            if sub == "stats":
                return self.memory_stats()
            if sub == "search":
                if not arg.strip():
                    return self._result(False, message="Usage: /memory search <keywords>", code="invalid")
                return self.memory_search(arg.strip())
            if sub == "delete":
                if not arg.strip().isdigit():
                    return self._result(False, message="Usage: /memory delete <id>", code="invalid")
                return self.memory_delete(int(arg.strip()))
            return self._result(False, message="Unknown /memory subcommand", code="invalid")

        if raw.startswith("/skill"):
            # Keep path args intact by splitting at most twice.
            parts = raw.split(maxsplit=2)
            sub = parts[1].lower() if len(parts) > 1 else "list"
            arg = parts[2] if len(parts) > 2 else ""
            if sub == "list":
                return self.skills_list()
            if sub == "reload":
                return self.skill_reload()
            if sub == "install":
                if not arg.strip():
                    return self._result(False, message="Usage: /skill install <url-or-path>", code="invalid")
                return self.skill_install(arg.strip())
            if sub == "remove":
                if not arg.strip():
                    return self._result(False, message="Usage: /skill remove <name>", code="invalid")
                return self.skill_remove(arg.strip())
            if sub == "info":
                if not arg.strip():
                    return self._result(False, message="Usage: /skill info <name>", code="invalid")
                return self.skill_info(arg.strip())
            if sub == "update":
                if not arg.strip():
                    return self._result(False, message="Usage: /skill update <name>", code="invalid")
                return self.skill_update(arg.strip())
            return self._result(False, message="Unknown /skill subcommand", code="invalid")

        # Optional: parse quoted command payload as generic `/config KEY "value..."` fallback
        try:
            shlex.split(raw)
        except Exception:
            pass
        return self._result(False, message="Unknown command", code="unknown_command")
