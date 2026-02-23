"""Reminder skill — multi-timer manager with Windows toast notifications."""

META = {
    "name": "reminder",
    "version": "1.0.0",
    "description": "通用提醒系统：支持多个计时提醒、循环提醒、Windows 系统通知",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": (
                "设置一个提醒，到时间后弹出 Windows 通知。"
                "可设置一次性或循环重复提醒（每隔 N 分钟重复）"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "提醒内容，如 '去喝水'、'站起来活动'"},
                    "minutes": {
                        "type": "number",
                        "description": "多少分钟后提醒（支持小数，如 0.5 = 30秒）",
                    },
                    "repeat": {
                        "type": "boolean",
                        "description": "是否循环重复（每隔 minutes 重复一次），默认 false",
                        "default": False,
                    },
                    "label": {
                        "type": "string",
                        "description": "提醒标签（用于 list/cancel 时识别），默认使用 message 前 10 字",
                        "default": "",
                    },
                },
                "required": ["message", "minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "列出所有待触发的提醒，显示剩余时间和状态",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reminder",
            "description": "取消一个或所有提醒",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {
                        "type": "string",
                        "description": "提醒 ID（从 list_reminders 获取）；传 'all' 取消全部",
                    },
                },
                "required": ["reminder_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "snooze_reminder",
            "description": "将某个已存在的提醒延后指定分钟数",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string", "description": "提醒 ID"},
                    "extra_minutes": {
                        "type": "number",
                        "description": "再延后多少分钟，默认 5",
                        "default": 5,
                    },
                },
                "required": ["reminder_id"],
            },
        },
    },
]

import subprocess
import threading
import time

_lock = threading.Lock()
_reminders: dict[str, dict] = {}
_counter = 0
_CREATE_NO_WINDOW = 0x08000000


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"R{_counter:03d}"


def _toast(title: str, message: str) -> None:
    safe_msg = message.replace("'", "\\'")[:200]
    safe_title = title.replace("'", "\\'")[:50]
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $True; "
        f"$n.ShowBalloonTip(10000, '{safe_title}', '{safe_msg}', "
        "[System.Windows.Forms.ToolTipIcon]::Info); "
        "Start-Sleep -Seconds 11; "
        "$n.Dispose()"
    )
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception:
        pass


def _schedule(rid: str, interval_s: float, repeat: bool) -> None:
    """Schedule a timer for the given reminder ID."""

    def _fire():
        with _lock:
            rem = _reminders.get(rid)
            if not rem or not rem["active"]:
                return
            rem["fired_count"] = rem.get("fired_count", 0) + 1
            message = rem["message"]
            label = rem["label"]
            count = rem["fired_count"]

        suffix = f"（第 {count} 次）" if count > 1 else ""
        _toast(f"⏰ 提醒：{label}", message + suffix)

        if repeat:
            with _lock:
                rem = _reminders.get(rid)
                if rem and rem["active"]:
                    t = threading.Timer(interval_s, _fire)
                    t.daemon = True
                    t.start()
                    rem["timer"] = t
                    rem["next_fire"] = time.time() + interval_s
        else:
            with _lock:
                if rid in _reminders:
                    _reminders[rid]["active"] = False

    t = threading.Timer(interval_s, _fire)
    t.daemon = True
    t.start()
    return t


def execute(name: str, args: dict) -> dict:

    if name == "set_reminder":
        message = str(args["message"]).strip()
        minutes = float(args["minutes"])
        repeat = bool(args.get("repeat", False))
        label = str(args.get("label", "") or message[:10]).strip()

        if minutes <= 0:
            return {"ok": False, "result": "时间必须大于 0"}
        if minutes > 1440:
            return {"ok": False, "result": "最多支持 24 小时（1440 分钟）后提醒"}

        interval_s = minutes * 60
        rid = _next_id()

        with _lock:
            t = _schedule(rid, interval_s, repeat)
            _reminders[rid] = {
                "id": rid,
                "label": label,
                "message": message,
                "interval_s": interval_s,
                "repeat": repeat,
                "timer": t,
                "created": time.time(),
                "next_fire": time.time() + interval_s,
                "fired_count": 0,
                "active": True,
            }

        m_int = int(minutes)
        m_frac = int((minutes - m_int) * 60)
        time_str = f"{m_int} 分 {m_frac} 秒" if m_frac else f"{m_int} 分钟"
        repeat_str = "（循环重复）" if repeat else ""

        return {
            "ok": True,
            "result": (
                f"⏰ 提醒已设置 [{rid}]{repeat_str}\n"
                f"内容：{message}\n"
                f"将在 {time_str} 后触发"
            ),
        }

    if name == "list_reminders":
        with _lock:
            active = {k: v for k, v in _reminders.items() if v["active"]}

        if not active:
            return {"ok": True, "result": "当前没有待触发的提醒"}

        now = time.time()
        lines = [f"⏰ 待触发提醒（共 {len(active)} 个）:", ""]
        for rid, rem in sorted(active.items()):
            remaining = max(0, rem["next_fire"] - now)
            m, s = divmod(int(remaining), 60)
            h, m = divmod(m, 60)
            if h > 0:
                time_str = f"{h}h {m:02d}m {s:02d}s"
            else:
                time_str = f"{m:02d}m {s:02d}s"
            repeat_str = " [循环]" if rem["repeat"] else ""
            fired_str = f" (已触发{rem['fired_count']}次)" if rem["fired_count"] > 0 else ""
            lines.append(f"  [{rid}]{repeat_str}{fired_str}")
            lines.append(f"    内容：{rem['message'][:60]}")
            lines.append(f"    剩余：{time_str}")
            lines.append("")

        return {"ok": True, "result": "\n".join(lines)}

    if name == "cancel_reminder":
        rid = str(args["reminder_id"]).strip()

        if rid.lower() == "all":
            with _lock:
                cancelled = []
                for r_id, rem in list(_reminders.items()):
                    if rem["active"]:
                        if rem.get("timer"):
                            rem["timer"].cancel()
                        rem["active"] = False
                        cancelled.append(r_id)
                _reminders.clear()
            if not cancelled:
                return {"ok": True, "result": "当前没有活跃的提醒"}
            return {"ok": True, "result": f"已取消全部 {len(cancelled)} 个提醒：{', '.join(cancelled)}"}

        with _lock:
            rem = _reminders.get(rid)
            if not rem or not rem["active"]:
                return {"ok": False, "result": f"未找到活跃的提醒 [{rid}]，请用 list_reminders 查看当前提醒"}
            if rem.get("timer"):
                rem["timer"].cancel()
            rem["active"] = False

        return {"ok": True, "result": f"✅ 提醒 [{rid}]「{rem['message'][:40]}」已取消"}

    if name == "snooze_reminder":
        rid = str(args["reminder_id"]).strip()
        extra_min = float(args.get("extra_minutes", 5))

        with _lock:
            rem = _reminders.get(rid)
            if not rem or not rem["active"]:
                return {"ok": False, "result": f"未找到活跃的提醒 [{rid}]"}
            # Cancel old timer
            if rem.get("timer"):
                rem["timer"].cancel()
            # Extend
            extra_s = extra_min * 60
            rem["next_fire"] = time.time() + extra_s
            new_t = _schedule(rid, extra_s, rem["repeat"])
            rem["timer"] = new_t

        return {
            "ok": True,
            "result": f"😴 提醒 [{rid}] 已延后 {extra_min:.0f} 分钟",
        }

    return {"ok": False, "result": f"Unknown tool: {name}"}
