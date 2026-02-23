"""Dynamic skill plugin system for Starbot.

Skill format (a Python file placed in the skills/ directory):

    META = {
        "name": "skill_name",       # unique identifier
        "version": "1.0.0",
        "description": "...",
        "author": "...",
    }

    TOOLS = [                        # OpenAI function-calling schemas
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "...",
                "parameters": {
                    "type": "object",
                    "properties": {"arg": {"type": "string"}},
                    "required": ["arg"],
                },
            },
        }
    ]

    def execute(name: str, args: dict) -> dict:
        if name == "tool_name":
            return {"ok": True, "result": "..."}
"""

import importlib.util
import logging
import re
import threading
from pathlib import Path

import requests

log = logging.getLogger(__name__)
_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


class SkillManager:
    def __init__(self):
        _SKILLS_DIR.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._skills: dict[str, object] = {}    # skill_name -> module
        self._tool_index: dict[str, str] = {}   # tool_name -> skill_name
        self._load_all()

    # ──────────────────────────────────────────────────────────── loading

    def _load_all(self):
        for f in sorted(_SKILLS_DIR.glob("*.py")):
            if not f.name.startswith("_"):
                self._load_file(f)

    def _load_file(self, path: Path) -> bool:
        try:
            spec = importlib.util.spec_from_file_location(
                f"starbot_skill_{path.stem}", path
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if not hasattr(mod, "TOOLS") or not hasattr(mod, "execute"):
                log.warning("Skill %s skipped: missing TOOLS or execute()", path.name)
                return False

            meta = getattr(mod, "META", {})
            name = meta.get("name", path.stem)

            with self._lock:
                old = self._skills.get(name)
                if old:
                    for t in getattr(old, "TOOLS", []):
                        self._tool_index.pop(t["function"]["name"], None)
                self._skills[name] = mod
                for t in mod.TOOLS:
                    self._tool_index[t["function"]["name"]] = name

            log.info(
                "Skill loaded: %s v%s (%d tool(s))",
                name, meta.get("version", "?"), len(mod.TOOLS),
            )
            return True

        except Exception as e:
            log.error("Failed to load skill %s: %s", path.name, e)
            return False

    def reload(self):
        """Unload all skills and reload from disk."""
        with self._lock:
            self._skills.clear()
            self._tool_index.clear()
        self._load_all()

    # ─────────────────────────────────────────────────────────── install

    def install(self, source: str) -> tuple[bool, str]:
        """Install a skill from a URL or local file path.

        Supports:
        - Raw Python file URL  (ends with .py)
        - GitHub repo URL      (auto-finds skill.py / main.py in root)
        - Local file path
        """
        try:
            content = self._fetch_source(source)
        except Exception as e:
            return False, f"获取失败: {e}"

        if not content:
            return False, "内容为空"
        if "def execute" not in content or "TOOLS" not in content:
            return False, "不符合 skill 格式（需包含 TOOLS 列表和 execute 函数）"

        m = re.search(r'"name"\s*:\s*"([^"]+)"', content)
        raw_name = m.group(1) if m else Path(source.split("/")[-1]).stem
        skill_name = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name)

        dest = _SKILLS_DIR / f"{skill_name}.py"
        dest.write_text(content, encoding="utf-8")

        if self._load_file(dest):
            mod = self._skills.get(skill_name) or self._skills.get(raw_name)
            n_tools = len(getattr(mod, "TOOLS", [])) if mod else "?"
            return True, f"已安装 skill `{skill_name}`，共 {n_tools} 个工具"

        dest.unlink(missing_ok=True)
        return False, "文件已保存但加载失败，请检查格式"

    def _fetch_source(self, source: str) -> str:
        if not source.startswith("http"):
            return Path(source).read_text(encoding="utf-8")

        if "github.com" in source and not source.endswith(".py"):
            raw_base = source.rstrip("/").replace(
                "https://github.com/", "https://raw.githubusercontent.com/"
            )
            for candidate in [
                f"{raw_base}/main/skill.py",
                f"{raw_base}/master/skill.py",
                f"{raw_base}/main/main.py",
                f"{raw_base}/master/main.py",
            ]:
                try:
                    r = requests.get(candidate, timeout=10)
                    if r.ok and "def execute" in r.text:
                        return r.text
                except Exception:
                    continue
            raise ValueError("在仓库根目录未找到 skill.py 或 main.py")

        r = requests.get(source, timeout=10)
        r.raise_for_status()
        return r.text

    # ──────────────────────────────────────────────────────────── remove

    def remove(self, name: str) -> tuple[bool, str]:
        """Uninstall a skill by its name (META['name'] or file stem)."""
        target: Path | None = None
        for f in _SKILLS_DIR.glob("*.py"):
            mod = self._skills.get(name) or self._skills.get(f.stem)
            if f.stem == name or (
                mod and getattr(mod, "META", {}).get("name") == name
            ):
                target = f
                break

        if target is None:
            return False, f"未找到 skill: `{name}`"

        with self._lock:
            for key in (name, target.stem):
                mod = self._skills.pop(key, None)
                if mod:
                    for t in getattr(mod, "TOOLS", []):
                        self._tool_index.pop(t["function"]["name"], None)
                    break

        target.unlink()
        return True, f"已删除 skill `{name}`"

    # ─────────────────────────────────────────────────────────── execute

    def execute(self, tool_name: str, args: dict) -> dict | None:
        """Route a tool call to the appropriate skill. Returns None if unknown."""
        skill_name = self._tool_index.get(tool_name)
        if skill_name is None:
            return None
        mod = self._skills.get(skill_name)
        if mod is None:
            return None
        try:
            return mod.execute(tool_name, args)
        except Exception as e:
            log.error("Skill %s raised during execute(%s): %s", skill_name, tool_name, e)
            return {"ok": False, "result": f"Skill 执行出错: {e}"}

    # ──────────────────────────────────────────────────────────── query

    @property
    def tools_schema(self) -> list[dict]:
        with self._lock:
            schema: list[dict] = []
            for mod in self._skills.values():
                schema.extend(getattr(mod, "TOOLS", []))
            return schema

    def list_skills(self) -> list[dict]:
        with self._lock:
            out = []
            for name, mod in self._skills.items():
                meta = getattr(mod, "META", {})
                out.append({
                    "name": meta.get("name", name),
                    "version": meta.get("version", "?"),
                    "description": meta.get("description", ""),
                    "author": meta.get("author", ""),
                    "tools": [t["function"]["name"] for t in getattr(mod, "TOOLS", [])],
                })
            return out
