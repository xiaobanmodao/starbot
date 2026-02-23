"""Pomodoro timer skill — Windows toast notification on completion."""

META = {
    "name": "pomodoro",
    "version": "1.0.0",
    "description": "番茄工作法计时器，时间到时弹出 Windows 系统通知",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "start_pomodoro",
            "description": (
                "开始一个番茄钟计时。时间到时弹出 Windows 通知。"
                "如已有计时器在运行，会先取消旧的再开始新的。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "integer",
                        "description": "计时分钟数，默认 25（标准番茄钟）",
                        "default": 25,
                    },
                    "label": {
                        "type": "string",
                        "description": "任务标签，如 '写代码'、'阅读'，默认 '工作'",
                        "default": "工作",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pomodoro_status",
            "description": "查询当前番茄钟状态：剩余时间、进度条、累计完成数",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_pomodoro",
            "description": "取消当前正在进行的番茄钟计时",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

import subprocess
import threading
import time

_lock = threading.Lock()
_state: dict = {
    "timer": None,
    "start": 0.0,
    "duration": 0,
    "label": "",
    "count": 0,
    "active": False,
}

# Windows: CREATE_NO_WINDOW flag suppresses the console window
_CREATE_NO_WINDOW = 0x08000000


def _toast(title: str, message: str) -> None:
    """Fire a Windows balloon tip notification via PowerShell."""
    safe_msg = message.replace("'", "\\'")
    safe_title = title.replace("'", "\\'")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $True; "
        f"$n.ShowBalloonTip(8000, '{safe_title}', '{safe_msg}', "
        "[System.Windows.Forms.ToolTipIcon]::Info); "
        "Start-Sleep -Seconds 9; "
        "$n.Dispose()"
    )
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception:
        pass


def _on_finish() -> None:
    with _lock:
        _state["active"] = False
        _state["count"] += 1
        count = _state["count"]
        label = _state["label"]
    _toast("🍅 番茄钟", f"{label} 时间到！已完成第 {count} 个番茄 🍅")


def _progress_bar(pct: int, width: int = 20) -> str:
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def execute(name: str, args: dict) -> dict:
    if name == "start_pomodoro":
        minutes = max(1, int(args.get("minutes", 25)))
        label = str(args.get("label", "工作"))
        with _lock:
            if _state["active"] and _state["timer"]:
                _state["timer"].cancel()
            t = threading.Timer(minutes * 60, _on_finish)
            t.daemon = True
            t.start()
            _state.update(
                timer=t,
                start=time.time(),
                duration=minutes * 60,
                label=label,
                active=True,
            )
            completed = _state["count"]
        return {
            "ok": True,
            "result": (
                f"🍅 番茄钟启动：{label}，{minutes} 分钟后通知\n"
                f"历史累计完成：{completed} 个"
            ),
        }

    if name == "pomodoro_status":
        with _lock:
            if not _state["active"]:
                return {
                    "ok": True,
                    "result": f"当前无活跃番茄钟，累计完成 {_state['count']} 个 🍅",
                }
            elapsed = time.time() - _state["start"]
            remaining = max(0.0, _state["duration"] - elapsed)
            pct = min(100, int(elapsed / _state["duration"] * 100))
            m, s = divmod(int(remaining), 60)
            return {
                "ok": True,
                "result": (
                    f"🍅 {_state['label']} 进行中\n"
                    f"剩余 {m:02d}:{s:02d}  [{_progress_bar(pct)}] {pct}%\n"
                    f"累计完成 {_state['count']} 个"
                ),
            }

    if name == "cancel_pomodoro":
        with _lock:
            if not _state["active"]:
                return {"ok": True, "result": "当前没有活跃的番茄钟"}
            if _state["timer"]:
                _state["timer"].cancel()
            _state["active"] = False
            _state["timer"] = None
        return {"ok": True, "result": "⏹️ 番茄钟已取消"}

    return {"ok": False, "result": f"Unknown tool: {name}"}
