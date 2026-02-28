from __future__ import annotations

import json
import logging
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from comms.local_service import LocalClientService

log = logging.getLogger(__name__)

WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui"


def _json_bytes(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class _ApiHandler(BaseHTTPRequestHandler):
    service_factory: Callable[[], LocalClientService] | None = None
    static_dir: Path = WEBUI_DIR

    server_version = "StarbotWebUI/0.1"

    @property
    def service(self) -> LocalClientService:
        if self.service_factory is None:
            raise RuntimeError("service_factory not configured")
        return self.service_factory()

    def log_message(self, fmt, *args):
        log.debug("webui %s - " + fmt, self.client_address[0], *args)

    # -------------------------------------------------------------- helpers

    def _send_json(self, payload: dict, status: int = 200):
        data = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path):
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        ctype = "application/octet-stream"
        if path.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        elif path.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif path.suffix == ".json":
            ctype = "application/json; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            n = 0
        raw = self.rfile.read(n) if n > 0 else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # -------------------------------------------------------------- routing

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/ping":
            return self._send_json({"ok": True, "message": "pong"})
        if path == "/api/chat/events":
            limit = int((qs.get("limit") or ["200"])[0])
            return self._send_json(self.service.poll_chat_events(limit=limit))
        if path == "/api/chat/sessions":
            return self._send_json(self.service.chat_sessions())
        if path == "/api/status":
            return self._send_json(self.service.status())
        if path == "/api/doctor":
            return self._send_json(self.service.doctor())
        if path == "/api/config":
            return self._send_json(self.service.config_get())
        if path == "/api/model/list":
            return self._send_json(self.service.model_list())
        if path == "/api/skills":
            return self._send_json(self.service.skills_list())
        if path == "/api/tasks":
            return self._send_json(self.service.tasks())
        if path == "/api/memory/list":
            category = (qs.get("category") or [""])[0]
            limit = int((qs.get("limit") or ["20"])[0])
            return self._send_json(self.service.memory_list(category=category, limit=limit))
        if path == "/api/memory/stats":
            return self._send_json(self.service.memory_stats())

        # static files
        if path in {"/", "/index.html"}:
            return self._send_file(self.static_dir / "index.html")
        rel = path.lstrip("/")
        file_path = (self.static_dir / rel).resolve()
        try:
            file_path.relative_to(self.static_dir.resolve())
        except Exception:
            return self.send_error(HTTPStatus.FORBIDDEN)
        if file_path.is_file():
            return self._send_file(file_path)
        return self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        payload = self._read_json()

        if path == "/api/chat/send":
            text = str(payload.get("text", ""))
            attachments = payload.get("attachments") or []
            return self._send_json(self.service.send_chat(text, attachments=attachments))
        if path == "/api/chat/stop":
            return self._send_json(self.service.stop_chat())
        if path == "/api/chat/confirm":
            approved = bool(payload.get("approved", False))
            return self._send_json(self.service.confirm_chat(approved))
        if path == "/api/chat/reset":
            return self._send_json(self.service.reset_chat())
        if path == "/api/chat/new":
            return self._send_json(self.service.chat_new_session(str(payload.get("title", ""))))
        if path == "/api/chat/switch":
            return self._send_json(self.service.chat_switch_session(str(payload.get("session_id", ""))))
        if path == "/api/chat/rename":
            return self._send_json(self.service.chat_rename_session(str(payload.get("session_id", "")), str(payload.get("title", ""))))
        if path == "/api/chat/delete":
            return self._send_json(self.service.chat_delete_session(str(payload.get("session_id", ""))))
        if path == "/api/chat/usage":
            return self._send_json(self.service.chat_usage())
        if path == "/api/command":
            return self._send_json(self.service.exec_command(str(payload.get("text", ""))))
        if path == "/api/screenshot":
            return self._send_json(self.service.screenshot())
        if path == "/api/model/set":
            return self._send_json(self.service.model_set(str(payload.get("name", ""))))
        if path == "/api/config/set":
            return self._send_json(self.service.config_set(str(payload.get("key", "")), str(payload.get("value", ""))))
        if path == "/api/config/bulk":
            values = payload.get("values")
            return self._send_json(self.service.config_update_many(values if isinstance(values, dict) else {}))
        if path == "/api/memory/search":
            return self._send_json(self.service.memory_search(str(payload.get("query", "")), int(payload.get("limit", 12) or 12)))
        if path == "/api/memory/delete":
            return self._send_json(self.service.memory_delete(int(payload.get("id", 0) or 0)))
        if path == "/api/skill/install":
            return self._send_json(self.service.skill_install(str(payload.get("source", ""))))
        if path == "/api/skill/remove":
            return self._send_json(self.service.skill_remove(str(payload.get("name", ""))))
        if path == "/api/skill/info":
            return self._send_json(self.service.skill_info(str(payload.get("name", ""))))
        if path == "/api/skill/update":
            return self._send_json(self.service.skill_update(str(payload.get("name", ""))))
        if path == "/api/skill/reload":
            return self._send_json(self.service.skill_reload())
        if path == "/api/rollback":
            return self._send_json(self.service.rollback(int(payload.get("count", 1) or 1)))

        return self._send_json({"ok": False, "message": "Unknown endpoint", "code": "not_found"}, status=404)


class WebUiServer:
    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        service: LocalClientService | None = None,
        static_dir: Path | None = None,
    ):
        self.host = host
        self.port = port
        self._service = service or LocalClientService()
        self.static_dir = Path(static_dir or WEBUI_DIR)
        self._thread: threading.Thread | None = None
        self._httpd: ThreadingHTTPServer | None = None

    def _build_handler(self):
        service = self._service
        static_path = self.static_dir

        class Handler(_ApiHandler):
            service_factory = staticmethod(lambda: service)

        Handler.static_dir = static_path
        return Handler

    def start(self):
        if self._httpd is not None:
            return
        handler = self._build_handler()
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        try:
            self.port = int(self._httpd.server_address[1])
        except Exception:
            pass
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True, name="starbot-webui")
        self._thread.start()

    def stop(self):
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        self._httpd = None
        self._thread = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"
