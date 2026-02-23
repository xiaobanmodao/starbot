import json
import subprocess
import time
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
import pyautogui
import requests
from PIL import ImageChops

from memory.store import MemoryStore
from core.task_manager import TaskManager
from core.skill_manager import SkillManager
from actions.input_win32 import (
    mouse_click, mouse_double_click, mouse_move, mouse_scroll,
    hotkey as win32_hotkey, key_press as win32_key_press, type_text as win32_type_text,
)

_memory = MemoryStore()
_task_mgr = TaskManager()
_skill_manager = SkillManager()
_screen_lock = threading.Lock()
_on_bg_task_done = None  # 可由外部注册：fn(task_info) -> None

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click at screen coordinates",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"]},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text via keyboard",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hotkey",
            "description": "Press a hotkey combination, e.g. ['ctrl','c']",
            "parameters": {
                "type": "object",
                "properties": {"keys": {"type": "array", "items": {"type": "string"}}},
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll at position. Positive=up, negative=down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "clicks": {"type": "integer"},
                },
                "required": ["x", "y", "clicks"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Take a screenshot and return it for analysis",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot_region",
            "description": "Take a screenshot of a specific region for closer inspection. Use when you need to see details in a small area.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "Left edge"},
                    "y": {"type": "integer", "description": "Top edge"},
                    "width": {"type": "integer", "description": "Region width"},
                    "height": {"type": "integer", "description": "Region height"},
                },
                "required": ["x", "y", "width", "height"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen_text",
            "description": "OCR: extract all visible text from the current screen. Much more accurate than reading text from screenshots visually.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in the default browser",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_clipboard",
            "description": "Read current clipboard text content",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "double_click",
            "description": "Double-click at screen coordinates (open files, select words)",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_to",
            "description": "Move mouse to coordinates (hover to see tooltips)",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "drag",
            "description": "Drag from (x1,y1) to (x2,y2)",
            "parameters": {
                "type": "object",
                "properties": {
                    "x1": {"type": "integer"},
                    "y1": {"type": "integer"},
                    "x2": {"type": "integer"},
                    "y2": {"type": "integer"},
                },
                "required": ["x1", "y1", "x2", "y2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "key_press",
            "description": "Press a single key (enter, escape, tab, up, down, left, right, delete, backspace, f1-f12, etc.)",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Wait for specified seconds (for page loading, animations)",
            "parameters": {
                "type": "object",
                "properties": {"seconds": {"type": "number", "minimum": 0.1, "maximum": 30}},
                "required": ["seconds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "watch_screen",
            "description": "Periodically screenshot the screen to observe changes (e.g. watching a video). Returns key frames where the screen changed significantly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration": {"type": "integer", "description": "Total seconds to watch", "minimum": 5, "maximum": 120},
                    "interval": {"type": "number", "description": "Seconds between captures", "minimum": 1, "maximum": 15},
                },
                "required": ["duration"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_subtitles",
            "description": "Extract subtitles from a video URL. Returns text in chunks. Use offset to read subsequent chunks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Video URL"},
                    "lang": {"type": "string", "description": "Subtitle language code (zh, en, etc.)", "default": "zh"},
                    "offset": {"type": "integer", "description": "Character offset for reading subsequent chunks", "default": 0},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command and return output",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and return results with URLs. Use fetch_page to read full content of any result.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "Fetch and extract the main text content of a webpage. Use after web_search to deeply read articles, docs, or any URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "offset": {"type": "integer", "description": "Skip first N characters, for reading long pages in chunks", "default": 0},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_save",
            "description": (
                "Save information to long-term memory.\n"
                "Categories: preference(用户偏好), knowledge(知识/笔记), "
                "project(项目信息), experience(技术经验), bug(踩坑记录), todo(待办事项)\n"
                "importance 1-10: 越重要越高（默认5），重要事项设8-10以便优先检索"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["preference", "knowledge", "project", "experience", "bug", "todo"],
                    },
                    "content": {"type": "string"},
                    "importance": {
                        "type": "integer",
                        "description": "重要性 1-10，默认 5",
                        "default": 5,
                    },
                },
                "required": ["category", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_recall",
            "description": "Search long-term memory for relevant information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bg_task",
            "description": "Launch a background task that runs independently. Use for: learning videos, web research, long scans, etc. You can continue chatting while it runs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short task name"},
                    "prompt": {"type": "string", "description": "What the background task should do"},
                },
                "required": ["name", "prompt"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "task_status",
            "description": "Check status of all background tasks",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done",
            "description": "Signal that the task is complete",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read a file's text content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "default": 0, "description": "Character offset for large files"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Write text content to a file. mode='overwrite' replaces the file, mode='append' adds to the end.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "mode": {"type": "string", "enum": ["overwrite", "append"], "default": "overwrite"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_list",
            "description": "List files and directories in a path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "pattern": {"type": "string", "description": "Optional glob pattern, e.g. *.txt"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_search",
            "description": "Search for files containing specific text content. Returns matching file paths and line snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory to search in"},
                    "query": {"type": "string", "description": "Text to search for"},
                    "pattern": {"type": "string", "description": "File glob pattern, e.g. *.txt", "default": "*"},
                },
                "required": ["path", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "window_list",
            "description": "List all visible windows with their titles",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "window_focus",
            "description": "Bring a window to foreground by title (partial match)",
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "window_resize",
            "description": "Maximize, minimize, or restore a window by title (partial match)",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "state": {"type": "string", "enum": ["maximize", "minimize", "restore"]},
                },
                "required": ["title", "state"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_text",
            "description": "Wait until specific text appears on screen (OCR polling). Returns when found or timeout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to wait for"},
                    "timeout": {"type": "integer", "description": "Max seconds to wait", "default": 15},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "learn_video",
            "description": "Fully learn a video in one call: extract subtitles, summarize all content, save structured notes to memory. Much faster than get_subtitles + manual processing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Video URL (YouTube, Bilibili, etc.)"},
                    "topic": {"type": "string", "description": "What to focus on when summarizing"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "learn_url",
            "description": "Fully learn a webpage in one call: crawl full content, extract key information, save to memory. Much faster than fetch_page + manual processing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "topic": {"type": "string", "description": "What to focus on when extracting"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_research",
            "description": "一步完成：搜索 + 并行抓取多个来源 + AI 摘要。比 web_search + 多次 fetch_page 快数倍。适合需要综合多来源信息的研究型任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索词"},
                    "topic": {"type": "string", "description": "摘要时的关注重点"},
                    "n_sources": {"type": "integer", "description": "并行读取的来源数量（1-5），默认3", "default": 3},
                    "save": {"type": "boolean", "description": "是否将摘要存入长期记忆，默认 false", "default": False},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_delete",
            "description": "Delete a file or empty directory",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_clipboard",
            "description": "Set clipboard text content",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "process_list",
            "description": "List running processes with PID, name, CPU%, memory%",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "process_kill",
            "description": "Kill a process by PID or name",
            "parameters": {
                "type": "object",
                "properties": {
                    "pid": {"type": "integer", "description": "Process ID"},
                    "name": {"type": "string", "description": "Process name (kills all matching)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify",
            "description": "Show a Windows desktop notification (toast)",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["title", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_screen_size",
            "description": "Get screen resolution width and height",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_position",
            "description": "Get current mouse cursor position",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot_window",
            "description": "Take a screenshot of a specific window by title (partial match)",
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_image",
            "description": "Find a saved image on screen and return its center coordinates. Use to locate buttons/icons reliably.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Path to the template image file"},
                    "confidence": {"type": "number", "description": "Match confidence 0-1, default 0.8"},
                },
                "required": ["image_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_request",
            "description": "Send an HTTP request (GET/POST/PUT/DELETE) and return response. Use for APIs, webhooks, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                    "url": {"type": "string"},
                    "headers": {"type": "object", "description": "Optional request headers"},
                    "body": {"type": "string", "description": "Request body (JSON string or plain text)"},
                },
                "required": ["method", "url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zip_files",
            "description": "Create a zip archive from files/directories",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {"type": "array", "items": {"type": "string"}, "description": "Files/dirs to include"},
                    "output": {"type": "string", "description": "Output zip file path"},
                },
                "required": ["paths", "output"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unzip",
            "description": "Extract a zip archive",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Zip file path"},
                    "dest": {"type": "string", "description": "Destination directory"},
                },
                "required": ["path", "dest"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_env",
            "description": "Get environment variable value",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registry_read",
            "description": "Read a Windows registry value",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Full key path, e.g. HKEY_CURRENT_USER\\Software\\..."},
                    "value": {"type": "string", "description": "Value name (empty string for default)"},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registry_write",
            "description": "Write a Windows registry value",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "data": {"type": "string"},
                    "type": {"type": "string", "enum": ["REG_SZ", "REG_DWORD", "REG_EXPAND_SZ", "REG_MULTI_SZ", "REG_BINARY"], "description": "Registry value type, default REG_SZ"},
                },
                "required": ["key", "value", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registry_delete_value",
            "description": "Delete a Windows registry value",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Full key path, e.g. HKEY_CURRENT_USER\\Software\\..."},
                    "value": {"type": "string", "description": "Value name to delete"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registry_list_keys",
            "description": "List subkeys of a Windows registry key",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Full key path, e.g. HKEY_CURRENT_USER\\Software\\..."},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "power",
            "description": "System power action: shutdown, restart, sleep, lock screen, or cancel pending shutdown",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["shutdown", "restart", "sleep", "lock", "cancel"]},
                    "delay": {"type": "integer", "description": "Delay in seconds before action, default 0"},
                },
                "required": ["action"],
            },
        },
    },
]

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOT_PATH = os.path.join(_BASE_DIR, "logs", "screen.jpg")
os.makedirs(os.path.join(_BASE_DIR, "logs"), exist_ok=True)

_SCREENSHOT_MAX_WIDTH = 960
_WATCH_CHANGE_RATIO = 0.01
_TEXT_CHUNK = 6_000
_DISCORD_EMBED_MAX = 4000

_page_cache: dict = {}          # url -> (text, timestamp)
_page_cache_lock = threading.Lock()
_PAGE_CACHE_TTL = 300           # 5 minutes

_SCREEN_TOOL_NAMES = {
    "click", "double_click", "drag", "type_text", "hotkey", "key_press",
    "move_to", "scroll", "screenshot", "screenshot_region", "read_screen_text",
    "watch_screen", "wait_for_text", "window_list", "window_focus", "window_resize",
}
# 后台任务可用的工具（不含屏幕操作，避免与前台任务冲突）
BG_TOOLS_SCHEMA = [t for t in TOOLS_SCHEMA if t["function"]["name"] not in _SCREEN_TOOL_NAMES]


def get_tools_schema() -> list[dict]:
    """Built-in tools + dynamically loaded skill tools."""
    return TOOLS_SCHEMA + _skill_manager.tools_schema


def get_bg_tools_schema() -> list[dict]:
    """Built-in background tools + skill tools (screen tools excluded)."""
    skill_tools = [
        t for t in _skill_manager.tools_schema
        if t["function"]["name"] not in _SCREEN_TOOL_NAMES
    ]
    return BG_TOOLS_SCHEMA + skill_tools


# ---- Web helpers (search, extraction, cache) ----

def _search_ddg(query: str) -> list[dict]:
    """DuckDuckGo HTML search. Returns list of {title, url, snippet}."""
    import urllib.parse
    from html.parser import HTMLParser
    try:
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
    except Exception:
        return []
    items: list[dict] = []
    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self._mode = None
            self._buf = ""
            self._cur: dict = {}
        def handle_starttag(self, tag, attrs):
            d = dict(attrs)
            if tag == "a" and "result__a" in d.get("class", ""):
                self._mode = "title"
                self._buf = ""
                href = d.get("href", "")
                m = re.search(r"uddg=([^&]+)", href)
                self._cur["url"] = urllib.parse.unquote(m.group(1)) if m else href
            elif "result__snippet" in d.get("class", ""):
                self._mode = "snippet"
                self._buf = ""
        def handle_endtag(self, tag):
            if self._mode == "title" and tag == "a":
                self._cur["title"] = self._buf.strip()
                self._mode = None
            elif self._mode == "snippet" and tag in ("a", "td", "div", "span"):
                self._cur["snippet"] = self._buf.strip()
                if self._cur.get("title") and self._cur.get("url"):
                    items.append(dict(self._cur))
                self._cur = {}
                self._mode = None
        def handle_data(self, data):
            if self._mode:
                self._buf += data
    _P().feed(r.text)
    return items[:8]


def _search_bing(query: str) -> list[dict]:
    """Bing search fallback. Returns list of {title, url, snippet}."""
    try:
        resp = requests.get(
            "https://www.bing.com/search",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=10,
        )
    except Exception:
        return []
    items: list[dict] = []
    for m in re.finditer(
        r'<h2[^>]*>\s*<a[^>]+href="(https?://[^"&]+)"[^>]*>(.*?)</a>',
        resp.text, re.DOTALL,
    ):
        url = m.group(1)
        title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if title and not any(s in url for s in ("bing.com", "microsoft.com", "msn.com")):
            items.append({"title": title, "url": url, "snippet": ""})
    return items[:8]


def _do_web_search(query: str) -> list[dict]:
    """Search with DDG, fall back to Bing if empty."""
    results = _search_ddg(query)
    if not results:
        results = _search_bing(query)
    return results


def _extract_html_text(html: str) -> str:
    """Extract main content from HTML. Uses trafilatura if installed, else tag-stripping."""
    try:
        import trafilatura
        text = trafilatura.extract(
            html, include_comments=False, include_tables=True, no_fallback=False,
        )
        if text and len(text.strip()) > 100:
            return re.sub(r'\n{3,}', '\n\n', text).strip()
    except ImportError:
        pass
    from html.parser import HTMLParser
    class _T(HTMLParser):
        def __init__(self):
            super().__init__()
            self._skip = False
            self._parts: list[str] = []
        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "nav", "footer", "head", "aside"):
                self._skip = True
        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "footer", "head", "aside"):
                self._skip = False
            if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr"):
                self._parts.append("\n")
        def handle_data(self, data):
            if not self._skip and data.strip():
                self._parts.append(data)
    p = _T()
    p.feed(html)
    return re.sub(r'\n{3,}', '\n\n', "".join(p._parts)).strip()


def _fetch_url_text(url: str) -> str:
    """Fetch a URL and extract its main text content, with a 5-minute cache."""
    now = time.time()
    with _page_cache_lock:
        cached = _page_cache.get(url)
        if cached and now - cached[1] < _PAGE_CACHE_TTL:
            return cached[0]
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            resp.encoding = resp.apparent_encoding
            text = _extract_html_text(resp.text)
            break
        except Exception as e:
            last_err = e
            time.sleep(1.5 ** attempt)
    else:
        return ""
    with _page_cache_lock:
        _page_cache[url] = (text, time.time())
    return text


def execute(action: dict) -> dict:
    """Execute a single action and return a structured result."""
    name = action["name"]
    args = action.get("arguments", {})
    if isinstance(args, str):
        args = json.loads(args)

    # 坐标越界检查
    if name in ("click", "double_click", "move_to", "scroll"):
        sw, sh = pyautogui.size()
        x, y = args.get("x", 0), args.get("y", 0)
        if not (0 <= x < sw and 0 <= y < sh):
            return {"ok": False, "result": f"坐标 ({x},{y}) 超出屏幕范围 ({sw}x{sh})"}
    elif name == "drag":
        sw, sh = pyautogui.size()
        for px, py in [(args.get("x1",0), args.get("y1",0)), (args.get("x2",0), args.get("y2",0))]:
            if not (0 <= px < sw and 0 <= py < sh):
                return {"ok": False, "result": f"坐标 ({px},{py}) 超出屏幕范围 ({sw}x{sh})"}

    SCREEN_ACTIONS = {
        "click", "double_click", "drag", "type_text", "hotkey",
        "key_press", "move_to", "scroll", "screenshot",
        "screenshot_region", "read_screen_text", "wait_for_text",
        # watch_screen is excluded: it handles _screen_lock internally to avoid
        # holding the lock during sleep intervals
    }
    if name in SCREEN_ACTIONS:
        with _screen_lock:
            return _do_execute(name, args)
    return _do_execute(name, args)


def _do_execute(name: str, args: dict) -> dict:
    """实际执行逻辑。"""
    try:
        if name == "click":
            mouse_click(args["x"], args["y"], args.get("button", "left"))
            return {"ok": True, "result": f"Clicked ({args['x']},{args['y']})"}

        elif name == "type_text":
            win32_type_text(args["text"])
            return {"ok": True, "result": f"Typed {len(args['text'])} chars"}

        elif name == "hotkey":
            win32_hotkey(*args["keys"])
            return {"ok": True, "result": f"Pressed {'+'.join(args['keys'])}"}

        elif name == "scroll":
            mouse_scroll(args["x"], args["y"], args["clicks"])
            return {"ok": True, "result": f"Scrolled {args['clicks']}"}

        elif name == "double_click":
            mouse_double_click(args["x"], args["y"])
            return {"ok": True, "result": f"Double-clicked ({args['x']},{args['y']})"}

        elif name == "move_to":
            mouse_move(args["x"], args["y"])
            return {"ok": True, "result": f"Moved to ({args['x']},{args['y']})"}

        elif name == "drag":
            from actions.input_win32 import mouse_click, mouse_move
            import ctypes
            mouse_move(args["x1"], args["y1"])
            # 用 SendInput 发送 mousedown，比 mouse_event 更可靠
            from actions.input_win32 import _send, INPUT, _INPUT_UNION, MOUSEINPUT, INPUT_MOUSE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_ABSOLUTE, _screen_to_absolute
            ax1, ay1 = _screen_to_absolute(args["x1"], args["y1"])
            ax2, ay2 = _screen_to_absolute(args["x2"], args["y2"])
            _send(INPUT(type=INPUT_MOUSE, _u=_INPUT_UNION(mi=MOUSEINPUT(
                dx=ax1, dy=ay1, mouseData=0, dwFlags=MOUSEEVENTF_LEFTDOWN|MOUSEEVENTF_ABSOLUTE, time=0, dwExtraInfo=None))))
            time.sleep(0.05)
            mouse_move(args["x2"], args["y2"])
            time.sleep(0.05)
            _send(INPUT(type=INPUT_MOUSE, _u=_INPUT_UNION(mi=MOUSEINPUT(
                dx=ax2, dy=ay2, mouseData=0, dwFlags=MOUSEEVENTF_LEFTUP|MOUSEEVENTF_ABSOLUTE, time=0, dwExtraInfo=None))))
            return {"ok": True, "result": f"Dragged ({args['x1']},{args['y1']}) -> ({args['x2']},{args['y2']})"}

        elif name == "key_press":
            win32_key_press(args["key"])
            return {"ok": True, "result": f"Pressed {args['key']}"}

        elif name == "wait":
            time.sleep(args["seconds"])
            return {"ok": True, "result": f"Waited {args['seconds']}s"}

        elif name == "watch_screen":
            duration = args["duration"]
            interval = args.get("interval", 3)
            frames_dir = os.path.join(_BASE_DIR, "logs", "frames")
            os.makedirs(frames_dir, exist_ok=True)
            for old in os.listdir(frames_dir):
                if old.endswith(".png"):
                    os.remove(os.path.join(frames_dir, old))
            prev_gray = None
            key_frames = []
            end_time = time.time() + duration
            while time.time() < end_time:
                # Hold lock only during screenshot; release before sleep
                with _screen_lock:
                    img = pyautogui.screenshot()
                # 缩放到最大宽度再比较，减少计算量
                sw = _SCREENSHOT_MAX_WIDTH
                sh = int(img.height * sw / img.width)
                small = img.resize((sw, sh))
                gray = small.convert("L")
                if prev_gray is None:
                    path = f"{frames_dir}/frame_{len(key_frames):03d}.png"
                    small.save(path)
                    key_frames.append(path)
                else:
                    diff = ImageChops.difference(gray, prev_gray)
                    # 用 getbbox 快速判断是否有变化区域，比 sum(getdata()) 快很多
                    bbox = diff.point(lambda p: 255 if p > 10 else 0).getbbox()
                    if bbox:
                        bw = bbox[2] - bbox[0]
                        bh = bbox[3] - bbox[1]
                        change_ratio = (bw * bh) / (sw * sh)
                        if change_ratio > _WATCH_CHANGE_RATIO:
                            path = f"{frames_dir}/frame_{len(key_frames):03d}.png"
                            small.save(path)
                            key_frames.append(path)
                prev_gray = gray
                time.sleep(interval)  # sleep outside lock
            # 返回所有关键帧路径供 AI 选择分析，以及最后一帧作为图像
            last = key_frames[-1] if key_frames else SCREENSHOT_PATH
            return {
                "ok": True,
                "result": f"Watched {duration}s, {len(key_frames)} key frames captured",
                "image": last,
            }

        elif name == "get_subtitles":
            url = args["url"]
            lang = args.get("lang", "zh")
            offset = args.get("offset", 0)
            out_dir = os.path.join(_BASE_DIR, "logs", "subs")
            os.makedirs(out_dir, exist_ok=True)
            # 如果是续读（offset>0），直接读已有字幕文件
            existing = [f for f in os.listdir(out_dir) if f.endswith(".srt")]
            if offset > 0 and existing:
                with open(os.path.join(out_dir, existing[0]), "r", encoding="utf-8", errors="ignore") as fh:
                    sub_text = fh.read()
            else:
                for f in os.listdir(out_dir):
                    os.remove(os.path.join(out_dir, f))
                for try_lang in [lang, "en"]:
                    subprocess.run(
                        ["yt-dlp", "--skip-download", "--write-auto-sub", "--write-sub",
                         "--sub-lang", try_lang, "--sub-format", "srt", "--convert-subs", "srt",
                         "-o", f"{out_dir}/sub", url],
                        capture_output=True, text=True, timeout=60,
                    )
                    srt_files = [f for f in os.listdir(out_dir) if f.endswith(".srt")]
                    if srt_files:
                        break
                srt_files = [f for f in os.listdir(out_dir) if f.endswith(".srt")]
                if not srt_files:
                    return {"ok": False, "result": "No subtitles found"}
                with open(os.path.join(out_dir, srt_files[0]), "r", encoding="utf-8", errors="ignore") as fh:
                    sub_text = fh.read()
            lines = [l for l in sub_text.splitlines()
                     if l.strip() and not l.strip().isdigit()
                     and not re.match(r'\d{2}:\d{2}', l.strip())]
            clean = "\n".join(dict.fromkeys(lines))
            total = len(clean)
            segment = clean[offset:offset + _TEXT_CHUNK]
            remaining = max(0, total - offset - _TEXT_CHUNK)
            result = {"ok": True, "result": segment, "total_chars": total, "offset": offset}
            if remaining > 0:
                result["note"] = f"还有 {remaining} 字符，下次调用传 offset={offset + _TEXT_CHUNK}"
            return result

        elif name == "screenshot":
            img = pyautogui.screenshot()
            from PIL import ImageDraw
            w, h = img.size
            # 缩放到最大宽度
            if w > _SCREENSHOT_MAX_WIDTH:
                scale = _SCREENSHOT_MAX_WIDTH / w
                img = img.resize((_SCREENSHOT_MAX_WIDTH, int(h * scale)))
                w, h = img.size
            draw = ImageDraw.Draw(img)
            sw, sh = pyautogui.size()
            scale_x = w / sw
            scale_y = h / sh
            step = 200
            for x in range(0, w, step):
                draw.line([(x, 0), (x, h)], fill=(255, 0, 0, 80), width=1)
                draw.text((x + 2, 2), str(int(x / scale_x)), fill=(255, 0, 0))
            for y in range(0, h, step):
                draw.line([(0, y), (w, y)], fill=(255, 0, 0, 80), width=1)
                draw.text((2, y + 2), str(int(y / scale_y)), fill=(255, 0, 0))
            img.convert("RGB").save(SCREENSHOT_PATH, "JPEG", quality=75, optimize=True)
            return {"ok": True, "result": f"Screenshot taken ({pyautogui.size()[0]}x{pyautogui.size()[1]}, displayed at {w}x{h})", "image": SCREENSHOT_PATH}

        elif name == "screenshot_region":
            region = (args["x"], args["y"], args["width"], args["height"])
            img = pyautogui.screenshot(region=region)
            if img.width < 800:
                scale = min(800 / img.width, 3.0)
                img = img.resize((int(img.width * scale), int(img.height * scale)))
            path = SCREENSHOT_PATH.replace(".jpg", "_region.jpg")
            img.convert("RGB").save(path, "JPEG", quality=75, optimize=True)
            return {"ok": True, "result": f"Region screenshot ({args['width']}x{args['height']})", "image": path}

        elif name == "read_screen_text":
            img = pyautogui.screenshot()
            try:
                import pytesseract
                text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            except (ImportError, Exception):
                return {"ok": False, "result": "OCR unavailable. Install tesseract: https://github.com/tesseract-ocr/tesseract and pip install pytesseract"}
            if not text.strip():
                return {"ok": False, "result": "OCR found no text on screen"}
            return {"ok": True, "result": text.strip()[:3000]}

        elif name == "open_url":
            import webbrowser
            webbrowser.open(args["url"])
            return {"ok": True, "result": f"Opened {args['url']}"}

        elif name == "get_clipboard":
            import ctypes
            ctypes.windll.user32.OpenClipboard(0)
            try:
                h = ctypes.windll.user32.GetClipboardData(13)  # CF_UNICODETEXT=13
                text = ctypes.wstring_at(h) if h else ""
            finally:
                ctypes.windll.user32.CloseClipboard()
            return {"ok": True, "result": text[:2000] if text else "(clipboard empty)"}

        elif name == "run_command":
            r = subprocess.run(
                args["command"], shell=True, capture_output=True, text=True, timeout=30,
            )
            output = (r.stdout + r.stderr).strip()[:2000]
            return {"ok": r.returncode == 0, "result": output or "(no output)"}

        elif name == "web_search":
            results = _do_web_search(args["query"])
            if not results:
                return {"ok": False, "result": "搜索失败或无结果"}
            out = "\n".join(
                f"{i+1}. {r['title']}\n   {r['url']}\n   {r.get('snippet','')}"
                for i, r in enumerate(results)
            )
            return {"ok": True, "result": out}

        elif name == "fetch_page":
            url = args["url"]
            offset = args.get("offset", 0)
            text = _fetch_url_text(url)
            if not text:
                return {"ok": False, "result": f"页面获取失败: {url}"}
            segment = text[offset:offset + _TEXT_CHUNK]
            remaining = max(0, len(text) - offset - _TEXT_CHUNK)
            result = {"ok": True, "result": segment, "total_chars": len(text), "offset": offset}
            if remaining > 0:
                result["note"] = f"还有 {remaining} 字符未读，下次调用传 offset={offset + _TEXT_CHUNK}"
            return result

        elif name == "memory_save":
            importance = int(args.get("importance", 5))
            saved = _memory.save(args["category"], args["content"], importance=importance)
            if saved:
                return {"ok": True, "result": f"Saved to {args['category']} (importance={importance})"}
            return {"ok": True, "result": f"Skipped (duplicate already exists in {args['category']})"}

        elif name == "memory_recall":
            results = _memory.search_multi(args["query"], args.get("limit", 5))
            if not results:
                return {"ok": True, "result": "No memories found"}
            # 只返回 category 和 content，去掉 created_at 等无用字段
            out = "\n---\n".join(f"[{r['category']}] {r['content']}" for r in results)
            return {"ok": True, "result": out}

        elif name == "bg_task":
            tid = _task_mgr.launch(args["name"], args["prompt"],
                                   on_done=_on_bg_task_done)
            return {"ok": True, "result": f"后台任务 #{tid} '{args['name']}' 已启动"}

        elif name == "task_status":
            return {"ok": True, "result": _task_mgr.summary()}

        elif name == "done":
            return {"ok": True, "done": True, "result": args.get("summary", "")}

        elif name == "learn_video":
            return _learn_video(args["url"], args.get("topic", ""))

        elif name == "file_read":
            path = args["path"]
            offset = args.get("offset", 0)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                segment = content[offset:offset + _TEXT_CHUNK]
                remaining = max(0, len(content) - offset - _TEXT_CHUNK)
                result = {"ok": True, "result": segment, "total_chars": len(content)}
                if remaining > 0:
                    result["note"] = f"还有 {remaining} 字符，下次传 offset={offset + _TEXT_CHUNK}"
                return result
            except FileNotFoundError:
                return {"ok": False, "result": f"文件不存在: {path}"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "file_write":
            path = args["path"]
            mode = "a" if args.get("mode") == "append" else "w"
            try:
                from core.op_log import backup_file, log_op
                backup = backup_file(path) if mode == "w" else None   # backup before overwrite
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, mode, encoding="utf-8") as f:
                    f.write(args["content"])
                log_op("file_write", path, backup, f"mode={mode}, len={len(args['content'])}")
                verb = "追加" if mode == "a" else "写入"
                note = f"（原文件已备份）" if backup else ""
                return {"ok": True, "result": f"已{verb} {len(args['content'])} 字符到 {path}{note}"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "file_list":
            import glob as _glob
            path = args["path"]
            pattern = args.get("pattern", "*")
            try:
                full = os.path.join(path, pattern)
                entries = _glob.glob(full)
                lines = []
                for e in sorted(entries)[:100]:
                    stat = os.stat(e)
                    kind = "📁" if os.path.isdir(e) else "📄"
                    lines.append(f"{kind} {os.path.basename(e)} ({stat.st_size} bytes)")
                return {"ok": True, "result": "\n".join(lines) or "(空目录)"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "file_search":
            import glob as _glob
            path = args["path"]
            query = args["query"].lower()
            pattern = args.get("pattern", "*")
            try:
                matches = []
                for fpath in sorted(_glob.glob(os.path.join(path, "**", pattern), recursive=True))[:200]:
                    if os.path.isdir(fpath):
                        continue
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            for lineno, line in enumerate(f, 1):
                                if query in line.lower():
                                    matches.append(f"{fpath}:{lineno}: {line.rstrip()[:120]}")
                                    if len(matches) >= 50:
                                        break
                    except Exception:
                        pass
                    if len(matches) >= 50:
                        break
                return {"ok": True, "result": "\n".join(matches) or "未找到匹配内容"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "window_list":
            import ctypes
            titles = []
            def _cb(hwnd, _):
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    buf = ctypes.create_unicode_buffer(256)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
                    if buf.value.strip():
                        titles.append(buf.value)
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(_cb), 0)
            return {"ok": True, "result": "\n".join(titles[:50])}

        elif name == "window_focus":
            import ctypes
            target = args["title"].lower()
            found = []
            def _cb(hwnd, _):
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
                if target in buf.value.lower() and ctypes.windll.user32.IsWindowVisible(hwnd):
                    found.append(hwnd)
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(_cb), 0)
            if not found:
                return {"ok": False, "result": f"未找到标题含 '{args['title']}' 的窗口"}
            hwnd = found[0]
            ctypes.windll.user32.ShowWindow(hwnd, 9)   # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
            return {"ok": True, "result": f"已切换到窗口: {buf.value}"}

        elif name == "window_resize":
            import ctypes
            target = args["title"].lower()
            state = args["state"]
            found = []
            def _cb(hwnd, _):
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
                if target in buf.value.lower() and ctypes.windll.user32.IsWindowVisible(hwnd):
                    found.append(hwnd)
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(_cb), 0)
            if not found:
                return {"ok": False, "result": f"未找到标题含 '{args['title']}' 的窗口"}
            hwnd = found[0]
            sw_map = {"maximize": 3, "minimize": 6, "restore": 9}
            ctypes.windll.user32.ShowWindow(hwnd, sw_map[state])
            return {"ok": True, "result": f"窗口已{state}"}

        elif name == "wait_for_text":
            target = args["text"]
            timeout = args.get("timeout", 15)
            end = time.time() + timeout
            while time.time() < end:
                img = pyautogui.screenshot()
                try:
                    import pytesseract
                    ocr = pytesseract.image_to_string(img, lang="chi_sim+eng")
                    if target in ocr:
                        return {"ok": True, "result": f"找到文字: '{target}'"}
                except Exception:
                    pass
                time.sleep(1)
            return {"ok": False, "result": f"超时 {timeout}s，未找到文字: '{target}'"}

        elif name == "learn_url":
            return _learn_url(args["url"], args.get("topic", ""))

        elif name == "web_research":
            query = args["query"]
            topic = args.get("topic", "")
            n = min(max(int(args.get("n_sources", 3)), 1), 5)
            save = args.get("save", False)

            search_results = _do_web_search(query)
            if not search_results:
                return {"ok": False, "result": "搜索无结果，请换个关键词"}

            sources = search_results[:n]

            def _fetch_one(r):
                text = _fetch_url_text(r["url"])
                if not text:
                    return ""
                return f"### {r['title']}\nURL: {r['url']}\n\n{text[:8000]}"

            with ThreadPoolExecutor(max_workers=n) as ex:
                pages = [p for p in ex.map(_fetch_one, sources) if p]

            if not pages:
                return {"ok": False, "result": "所有来源均无法获取内容"}

            combined = "\n\n---\n\n".join(pages)
            note = _llm_summarize(combined, topic, query)

            if save:
                _memory.save("knowledge", f"[网络研究] {query}\n{note}")

            sources_str = "\n".join(f"- {r['title']}: {r['url']}" for r in sources)
            return {"ok": True, "result": f"{note}\n\n**来源：**\n{sources_str}"}

        elif name == "file_delete":
            path = args["path"]
            try:
                from core.op_log import backup_file, log_op
                backup = backup_file(path)   # backup before delete
                if os.path.isdir(path):
                    os.rmdir(path)
                    backup = None   # dirs not backed up
                else:
                    os.remove(path)
                log_op("file_delete", path, backup)
                note = "（已备份，可用 /rollback 恢复）" if backup else ""
                return {"ok": True, "result": f"已删除: {path}{note}"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "set_clipboard":
            import ctypes
            text = args["text"]
            ctypes.windll.user32.OpenClipboard(0)
            try:
                ctypes.windll.user32.EmptyClipboard()
                h = ctypes.windll.kernel32.GlobalAlloc(0x0042, (len(text) + 1) * 2)
                p = ctypes.windll.kernel32.GlobalLock(h)
                ctypes.memmove(p, (text + "\0").encode("utf-16-le"), (len(text) + 1) * 2)
                ctypes.windll.kernel32.GlobalUnlock(h)
                ctypes.windll.user32.SetClipboardData(13, h)
            finally:
                ctypes.windll.user32.CloseClipboard()
            return {"ok": True, "result": f"已设置剪贴板: {text[:50]}"}

        elif name == "process_list":
            import psutil
            procs = []
            for p in sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                            key=lambda x: x.info["memory_percent"] or 0, reverse=True)[:30]:
                i = p.info
                procs.append(f"{i['pid']:6d}  {(i['cpu_percent'] or 0):5.1f}%  {(i['memory_percent'] or 0):5.1f}%  {i['name']}")
            return {"ok": True, "result": "   PID   CPU    MEM  NAME\n" + "\n".join(procs)}

        elif name == "process_kill":
            import psutil, signal
            pid = args.get("pid")
            pname = args.get("name", "").lower()
            killed = []
            if pid:
                try:
                    psutil.Process(pid).kill()
                    killed.append(str(pid))
                except Exception as e:
                    return {"ok": False, "result": str(e)}
            elif pname:
                for p in psutil.process_iter(["pid", "name"]):
                    if p.info["name"] and pname in p.info["name"].lower():
                        try:
                            p.kill()
                            killed.append(f"{p.info['name']}({p.info['pid']})")
                        except Exception:
                            pass
            if not killed:
                return {"ok": False, "result": "未找到匹配进程"}
            return {"ok": True, "result": f"已终止: {', '.join(killed)}"}

        elif name == "notify":
            try:
                import subprocess
                title = args["title"].replace("'", "\\'")
                msg = args["message"].replace("'", "\\'")
                subprocess.Popen(
                    ["powershell", "-WindowStyle", "Hidden", "-Command",
                     f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null;"
                     f"$t = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
                     f"$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($t);"
                     f"$x.GetElementsByTagName('text')[0].AppendChild($x.CreateTextNode('{title}')) | Out-Null;"
                     f"$x.GetElementsByTagName('text')[1].AppendChild($x.CreateTextNode('{msg}')) | Out-Null;"
                     f"$n = [Windows.UI.Notifications.ToastNotification]::new($x);"
                     f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Starbot').Show($n)"],
                    creationflags=0x08000000,
                )
                return {"ok": True, "result": f"通知已发送: {args['title']}"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "get_screen_size":
            sw, sh = pyautogui.size()
            return {"ok": True, "result": f"{sw}x{sh}"}

        elif name == "mouse_position":
            x, y = pyautogui.position()
            return {"ok": True, "result": f"({x}, {y})"}

        elif name == "screenshot_window":
            import ctypes
            target = args["title"].lower()
            found = []
            def _cb(hwnd, _):
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
                if target in buf.value.lower() and ctypes.windll.user32.IsWindowVisible(hwnd):
                    found.append(hwnd)
                return True
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(_cb), 0)
            if not found:
                return {"ok": False, "result": f"未找到窗口: {args['title']}"}
            hwnd = found[0]
            rect = ctypes.wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            x, y, w, h = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return {"ok": False, "result": "窗口尺寸无效"}
            img = pyautogui.screenshot(region=(x, y, w, h))
            base, ext = os.path.splitext(SCREENSHOT_PATH)
            path = f"{base}_window{ext or '.png'}"
            img.save(path)
            return {"ok": True, "result": f"窗口截图 {w}x{h}", "image": path}

        elif name == "find_image":
            try:
                loc = pyautogui.locateOnScreen(
                    args["image_path"], confidence=args.get("confidence", 0.8)
                )
                if loc is None:
                    return {"ok": False, "result": "未在屏幕上找到该图像"}
                cx, cy = pyautogui.center(loc)
                return {"ok": True, "result": f"找到位置: ({cx}, {cy})", "x": cx, "y": cy}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "http_request":
            method = args["method"].upper()
            url = args["url"]
            headers = args.get("headers") or {}
            body = args.get("body")
            last_err = None
            for attempt in range(3):
                try:
                    resp = requests.request(
                        method, url, headers=headers,
                        data=body.encode() if body else None,
                        timeout=15,
                    )
                    text = resp.text[:3000]
                    return {"ok": True, "result": f"HTTP {resp.status_code}\n{text}"}
                except Exception as e:
                    last_err = e
                    time.sleep(1.5 ** attempt)
            return {"ok": False, "result": f"请求失败: {last_err}"}

        elif name == "zip_files":
            import zipfile
            output = args["output"]
            try:
                with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
                    for p in args["paths"]:
                        if os.path.isdir(p):
                            for root, _, files in os.walk(p):
                                for f in files:
                                    fp = os.path.join(root, f)
                                    zf.write(fp, os.path.relpath(fp, os.path.dirname(p)))
                        else:
                            zf.write(p, os.path.basename(p))
                return {"ok": True, "result": f"已创建: {output}"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "unzip":
            import zipfile
            try:
                with zipfile.ZipFile(args["path"], "r") as zf:
                    zf.extractall(args["dest"])
                return {"ok": True, "result": f"已解压到: {args['dest']}"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "get_env":
            val = os.environ.get(args["name"])
            if val is None:
                return {"ok": False, "result": f"环境变量 {args['name']} 不存在"}
            return {"ok": True, "result": val}

        elif name == "registry_read":
            import winreg
            key_path = args["key"]
            value_name = args.get("value", "")
            roots = {"HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
                     "HKCU": winreg.HKEY_CURRENT_USER,
                     "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
                     "HKLM": winreg.HKEY_LOCAL_MACHINE,
                     "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT}
            root_name, sub = key_path.split("\\", 1)
            root = roots.get(root_name.upper())
            if not root:
                return {"ok": False, "result": f"未知根键: {root_name}"}
            try:
                with winreg.OpenKey(root, sub) as k:
                    data, _ = winreg.QueryValueEx(k, value_name)
                return {"ok": True, "result": str(data)}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "registry_write":
            import winreg
            key_path = args["key"]
            roots = {"HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
                     "HKCU": winreg.HKEY_CURRENT_USER,
                     "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
                     "HKLM": winreg.HKEY_LOCAL_MACHINE}
            root_name, sub = key_path.split("\\", 1)
            root = roots.get(root_name.upper())
            if not root:
                return {"ok": False, "result": f"未知根键: {root_name}"}
            try:
                reg_type_map = {
                    "REG_SZ": winreg.REG_SZ,
                    "REG_EXPAND_SZ": winreg.REG_EXPAND_SZ,
                    "REG_MULTI_SZ": winreg.REG_MULTI_SZ,
                    "REG_BINARY": winreg.REG_BINARY,
                    "REG_DWORD": winreg.REG_DWORD,
                }
                reg_type_str = args.get("type", "REG_SZ").upper()
                reg_type = reg_type_map.get(reg_type_str, winreg.REG_SZ)
                data = args["data"]
                if reg_type == winreg.REG_DWORD:
                    data = int(data)
                elif reg_type == winreg.REG_MULTI_SZ:
                    data = data.split("\n")
                with winreg.CreateKey(root, sub) as k:
                    winreg.SetValueEx(k, args["value"], 0, reg_type, data)
                return {"ok": True, "result": f"已写入注册表 ({reg_type_str})"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "power":
            action = args["action"]
            delay = args.get("delay", 0)
            if action == "cancel":
                r = subprocess.run("shutdown /a", shell=True, capture_output=True, text=True)
                if r.returncode == 0:
                    return {"ok": True, "result": "已取消待定的关机/重启"}
                return {"ok": False, "result": r.stderr.strip() or "没有待取消的关机任务"}
            cmds = {
                "shutdown": f"shutdown /s /t {delay}",
                "restart":  f"shutdown /r /t {delay}",
                "sleep":    "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
                "lock":     "rundll32.exe user32.dll,LockWorkStation",
            }
            cmd = cmds.get(action)
            if not cmd:
                return {"ok": False, "result": f"未知操作: {action}"}
            subprocess.run(cmd, shell=True)
            return {"ok": True, "result": f"已执行: {action}"}

        elif name == "registry_delete_value":
            import winreg
            key_path = args["key"]
            roots = {"HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
                     "HKCU": winreg.HKEY_CURRENT_USER,
                     "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
                     "HKLM": winreg.HKEY_LOCAL_MACHINE,
                     "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
                     "HKEY_USERS": winreg.HKEY_USERS}
            root_name, sub = key_path.split("\\", 1)
            root = roots.get(root_name.upper())
            if not root:
                return {"ok": False, "result": f"未知根键: {root_name}"}
            try:
                with winreg.OpenKey(root, sub, access=winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, args["value"])
                return {"ok": True, "result": f"已删除注册表值: {args['value']}"}
            except FileNotFoundError:
                return {"ok": False, "result": f"值不存在: {args['value']}"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        elif name == "registry_list_keys":
            import winreg
            key_path = args["key"]
            roots = {"HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
                     "HKCU": winreg.HKEY_CURRENT_USER,
                     "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
                     "HKLM": winreg.HKEY_LOCAL_MACHINE,
                     "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
                     "HKEY_USERS": winreg.HKEY_USERS}
            root_name, sub = key_path.split("\\", 1)
            root = roots.get(root_name.upper())
            if not root:
                return {"ok": False, "result": f"未知根键: {root_name}"}
            try:
                subkeys = []
                with winreg.OpenKey(root, sub) as k:
                    i = 0
                    while True:
                        try:
                            subkeys.append(winreg.EnumKey(k, i))
                            i += 1
                        except OSError:
                            break
                return {"ok": True, "result": "\n".join(subkeys) if subkeys else "(无子键)"}
            except Exception as e:
                return {"ok": False, "result": str(e)}

        else:
            # Try skill plugins before declaring unknown
            skill_result = _skill_manager.execute(name, args)
            if skill_result is not None:
                return skill_result
            return {"ok": False, "result": f"Unknown action: {name}"}

    except Exception as e:
        return {"ok": False, "result": str(e)}


_summarize_llm = None

def _get_summarize_llm():
    global _summarize_llm
    if _summarize_llm is None:
        from core.adapter import UniversalLLM
        from config import config
        _summarize_llm = UniversalLLM(config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL)
    return _summarize_llm

def _llm_summarize(text: str, topic: str, source: str) -> str:
    """用 LLM 对长文本分段摘要，各段并行处理后再合并，返回结构化笔记。"""
    llm = _get_summarize_llm()
    chunk_size = 8000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    total = len(chunks)

    def _do_chunk(args):
        i, chunk = args
        focus = f"重点关注：{topic}。" if topic else ""
        prompt = f"{focus}请提取以下内容的核心知识点，用简洁的条目列出（来源：{source}，第{i+1}/{total}段）：\n\n{chunk}"
        try:
            return llm.chat(prompt)
        except Exception:
            return chunk[:500]

    with ThreadPoolExecutor(max_workers=min(4, total)) as ex:
        summaries = list(ex.map(_do_chunk, enumerate(chunks)))

    if len(summaries) > 1:
        combined = "\n\n".join(summaries)
        focus = f"重点关注：{topic}。" if topic else ""
        final_prompt = f"{focus}将以下分段摘要整合为一份结构化笔记，包含：核心概念、关键步骤/方法、重要结论：\n\n{combined}"
        try:
            return llm.chat(final_prompt)
        except Exception:
            return combined
    return summaries[0] if summaries else ""


def _learn_video(url: str, topic: str) -> dict:
    """提取视频字幕并用 LLM 摘要，存入记忆。"""
    out_dir = os.path.join(_BASE_DIR, "logs", "subs")
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, f))

    # 尝试中文，失败则英文
    sub_text = ""
    for lang in ["zh", "en"]:
        subprocess.run(
            ["yt-dlp", "--skip-download", "--write-auto-sub", "--write-sub",
             "--sub-lang", lang, "--sub-format", "srt", "--convert-subs", "srt",
             "-o", f"{out_dir}/sub", url],
            capture_output=True, text=True, timeout=60,
        )
        srt_files = [f for f in os.listdir(out_dir) if f.endswith(".srt")]
        if srt_files:
            with open(os.path.join(out_dir, srt_files[0]), "r", encoding="utf-8", errors="ignore") as fh:
                sub_text = fh.read()
            break

    if not sub_text:
        return {"ok": False, "result": "No subtitles found. Try learn_url with the video page URL instead."}

    # 清理 SRT 格式
    lines = [l for l in sub_text.splitlines()
             if l.strip() and not l.strip().isdigit()
             and not re.match(r'\d{2}:\d{2}', l.strip())]
    clean = "\n".join(dict.fromkeys(lines))

    note = _llm_summarize(clean, topic, url)
    _memory.save("knowledge", f"[视频学习] {url}\n{note}")

    return {"ok": True, "result": f"学习完成，字幕 {len(clean)} 字符，已提炼摘要存入记忆。\n\n{note[:800]}"}


def _learn_url(url: str, topic: str) -> dict:
    """爬取网页全文并用 LLM 摘要，存入记忆。"""
    text = _fetch_url_text(url)
    if len(text) < 100:
        return {"ok": False, "result": "Page content too short or failed to extract"}
    note = _llm_summarize(text, topic, url)
    _memory.save("knowledge", f"[网页学习] {url}\n{note}")
    return {"ok": True, "result": f"学习完成，正文 {len(text)} 字符，已提炼摘要存入记忆。\n\n{note[:800]}"}
