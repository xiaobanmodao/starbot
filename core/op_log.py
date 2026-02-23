"""Operation log: auto-backup files before write/delete, undo support.

Usage in executor:
    from core.op_log import backup_file, log_op, get_history, undo_last
"""

import json
import logging
import shutil
import time
from pathlib import Path

log = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parent.parent
_BACKUP_DIR = _BASE / "logs" / "op_backups"
_LOG_FILE = _BASE / "logs" / "op_history.jsonl"
_MAX_BACKUPS = 20   # keep last 20 backup files


# ── Public API ────────────────────────────────────────────────────────────────

def backup_file(path: str) -> str | None:
    """Copy an existing file to the backup directory before it is modified.

    Returns the backup path on success, None if the file doesn't exist or
    the copy fails.
    """
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return None
        _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        backup_name = f"{ts}_{p.name}"
        backup_path = _BACKUP_DIR / backup_name
        shutil.copy2(p, backup_path)
        _prune_backups()
        return str(backup_path)
    except Exception as e:
        log.debug("backup_file failed for %s: %s", path, e)
        return None


def log_op(operation: str, path: str, backup_path: str | None = None, details: str = "") -> None:
    """Append one operation record to the JSONL history log."""
    try:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": int(time.time()),
            "op": operation,       # "file_write" | "file_delete" | ...
            "path": path,
            "backup": backup_path,
            "details": details,
        }
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.debug("log_op failed: %s", e)


def get_history(limit: int = 20) -> list[dict]:
    """Return the most recent `limit` operation records, newest first."""
    try:
        if not _LOG_FILE.exists():
            return []
        lines = _LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in reversed(lines[-200:]):   # parse at most last 200 lines
            try:
                entries.append(json.loads(line))
                if len(entries) >= limit:
                    break
            except Exception:
                pass
        return entries
    except Exception as e:
        log.debug("get_history failed: %s", e)
        return []


def undo_last(count: int = 1) -> list[str]:
    """Restore files from the most recent `count` backed-up operations.

    Returns a list of human-readable status messages.
    """
    history = get_history(50)
    messages: list[str] = []
    undone = 0

    for entry in history:
        if undone >= count:
            break
        backup = entry.get("backup")
        path = entry.get("path")
        if not backup or not path:
            continue
        try:
            backup_p = Path(backup)
            if not backup_p.exists():
                messages.append(f"⚠️ 备份文件已不存在：{backup}")
                continue
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_p, path)
            messages.append(f"✅ 已恢复：{path}")
            undone += 1
        except Exception as e:
            messages.append(f"❌ 恢复失败 {path}：{e}")

    if not messages:
        messages.append("没有可恢复的操作记录（需要先执行过带备份的文件操作）")
    return messages


def format_history(limit: int = 10) -> str:
    """Format recent history as a human-readable string for Discord display."""
    entries = get_history(limit)
    if not entries:
        return "（暂无操作记录）"

    from datetime import datetime
    lines = []
    for e in entries:
        ts = datetime.fromtimestamp(e["ts"]).strftime("%m-%d %H:%M")
        op = e.get("op", "?")
        path = e.get("path", "?")
        has_backup = "💾" if e.get("backup") else "  "
        lines.append(f"`{ts}` {has_backup} **{op}** `{path}`")
    return "\n".join(lines)


# ── Internal ──────────────────────────────────────────────────────────────────

def _prune_backups() -> None:
    """Delete oldest backup files when exceeding _MAX_BACKUPS."""
    try:
        files = sorted(_BACKUP_DIR.glob("*"), key=lambda f: f.stat().st_mtime)
        while len(files) > _MAX_BACKUPS:
            files.pop(0).unlink(missing_ok=True)
    except Exception:
        pass
