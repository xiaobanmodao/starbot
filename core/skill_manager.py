"""Dynamic skill plugin system for Starbot.

Supports two ecosystems:
1) Native Python skill plugins in ``skills/*.py`` (TOOLS + execute())
2) External ``SKILL.md``-style skills (e.g. Codex/Claude ecosystem)

External SKILL.md skills are exposed as callable tools so the model can pick
and use them on its own. The tool returns the skill instructions, file index,
and referenced resource snippets, allowing the model to follow the skill with
existing built-in tools (file/system/web actions).
"""

from __future__ import annotations

import importlib.util
import io
import logging
import re
import shutil
import threading
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_PY_SKILLS_DIR = _BASE_DIR / "skills"
_DEFAULT_EXT_SKILLS_DIR = _BASE_DIR / "skills_ext"


def _default_discovery_roots() -> list[Path]:
    roots: list[Path] = []
    home = Path.home()
    for p in [
        _BASE_DIR / ".codex" / "skills",
        home / ".codex" / "skills",
        _BASE_DIR / ".claude" / "skills",
        home / ".claude" / "skills",
    ]:
        if p not in roots:
            roots.append(p)
    return roots


def _safe_slug(value: str, *, lower: bool = True, max_len: int = 48) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", value or "").strip("_")
    if lower:
        s = s.lower()
    if not s:
        s = "skill"
    return s[:max_len].rstrip("_") or "skill"


def _read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except Exception:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _parse_skillmd_meta(text: str, fallback_name: str) -> dict:
    meta: dict[str, str] = {}
    body = text

    fm = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?", text, flags=re.DOTALL)
    if fm:
        body = text[fm.end():]
        for raw_line in fm.group(1).splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            key = k.strip().lower().replace("-", "_")
            val = v.strip().strip("'\"")
            if val.startswith("[") and val.endswith("]"):
                val = val[1:-1].strip()
            meta[key] = val

    # Fallback: first markdown heading
    if "name" not in meta:
        m = re.search(r"^\s*#\s+(.+?)\s*$", body, flags=re.MULTILINE)
        if m:
            meta["name"] = m.group(1).strip()

    # Fallback: first non-heading paragraph line
    if "description" not in meta:
        for line in body.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("#") or s.startswith(">") or s.startswith("```"):
                continue
            meta["description"] = s[:240]
            break

    meta.setdefault("name", fallback_name)
    meta.setdefault("description", "External SKILL.md skill")
    meta.setdefault("version", "skillmd")
    meta.setdefault("author", "")
    return meta


def _iter_candidate_skillmd_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    found: list[Path] = []
    for skill_md in root.rglob("SKILL.md"):
        p = skill_md.parent
        parts = {part.lower() for part in p.parts}
        if ".git" in parts or "__pycache__" in parts:
            continue
        # Skip Codex built-in/system skills by default; load user-downloaded ones.
        if ".system" in parts:
            continue
        found.append(p)
    found.sort(key=lambda p: (len(p.parts), str(p).lower()))
    return found


def _pick_skillmd_dir(candidates: list[Path]) -> tuple[Path | None, list[Path]]:
    if not candidates:
        return None, []
    if len(candidates) == 1:
        return candidates[0], candidates
    # Prefer the shallowest path (often repo root skill).
    best = sorted(candidates, key=lambda p: (len(p.parts), str(p).lower()))[0]
    return best, candidates


def _github_repo_zip_urls(owner: str, repo: str, branch_hint: str | None) -> list[str]:
    branches: list[str] = []
    if branch_hint:
        branches.append(branch_hint)
    for b in ("main", "master"):
        if b not in branches:
            branches.append(b)
    return [f"https://github.com/{owner}/{repo}/archive/refs/heads/{b}.zip" for b in branches]


def _parse_github_tree_url(url: str) -> tuple[str, str, str | None, str | None] | None:
    m = re.match(
        r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.*))?)?/?$",
        url,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    owner, repo, branch, subpath = m.group(1), m.group(2), m.group(3), m.group(4)
    return owner, repo, branch, (subpath or None)


class _MarkdownSkillAdapter:
    """Adapter exposing a SKILL.md directory as a callable tool."""

    def __init__(self, root: Path, meta: dict, tool_name: str):
        self._root = root
        self._skill_file = root / "SKILL.md"
        self._text = _read_text(self._skill_file)
        self.META = dict(meta)
        desc = str(meta.get("description", "")).strip()
        if len(desc) > 220:
            desc = desc[:217].rstrip() + "..."
        self.TOOLS = [{
            "type": "function",
            "function": {
                "name": tool_name,
                "description": (
                    f"Use external SKILL.md skill '{meta.get('name', root.name)}'. "
                    f"{desc}".strip()
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "What you want to do using this skill's instructions.",
                        },
                        "include_files": {
                            "type": "boolean",
                            "description": "Include file index and referenced file snippets from the skill directory.",
                            "default": True,
                        },
                    },
                    "required": ["task"],
                },
            },
        }]

    def execute(self, name: str, args: dict) -> dict:
        include_files = bool(args.get("include_files", True))
        task = str(args.get("task", "")).strip()
        if not task:
            return {"ok": False, "result": "Missing required argument: task"}

        lines: list[str] = [
            f"[External SKILL] {self.META.get('name', self._root.name)}",
            f"Skill root: {self._root}",
            f"Requested task: {task}",
            "",
            "Use the following SKILL.md instructions to complete the task. "
            "You may use built-in tools to read files under the skill root, run scripts, or inspect templates as needed.",
            "",
            "--- SKILL.md ---",
        ]

        skill_text = self._text.strip()
        if len(skill_text) > 16000:
            lines.append(skill_text[:16000] + "\n...[truncated]")
        else:
            lines.append(skill_text)

        if include_files:
            files = [
                p for p in sorted(self._root.rglob("*"))
                if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts
            ]
            if files:
                lines.extend(["", "--- Files (top) ---"])
                for p in files[:80]:
                    rel = p.relative_to(self._root).as_posix()
                    try:
                        size = p.stat().st_size
                    except Exception:
                        size = -1
                    lines.append(f"- {rel} ({size} bytes)")
                if len(files) > 80:
                    lines.append(f"- ... {len(files) - 80} more")

            refs: list[Path] = []
            seen: set[str] = set()
            for ref in re.findall(r"`([^`\n]+)`", self._text):
                if len(ref) > 180:
                    continue
                if ref.startswith(("http://", "https://")):
                    continue
                rp = (self._root / ref).resolve()
                try:
                    rp.relative_to(self._root.resolve())
                except Exception:
                    continue
                if rp.is_file():
                    key = str(rp).lower()
                    if key not in seen:
                        refs.append(rp)
                        seen.add(key)

            if refs:
                lines.extend(["", "--- Referenced file snippets ---"])
                total_chars = 0
                for p in refs[:5]:
                    rel = p.relative_to(self._root).as_posix()
                    text = _read_text(p)
                    if len(text) > 2500:
                        text = text[:2500] + "\n...[truncated]"
                    block = f"[{rel}]\n{text}\n"
                    if total_chars + len(block) > 9000:
                        break
                    lines.append(block)
                    total_chars += len(block)

        return {"ok": True, "result": "\n".join(lines)}


class SkillManager:
    def __init__(
        self,
        skills_dir: Path | None = None,
        ext_skills_dir: Path | None = None,
        discovery_roots: list[Path] | None = None,
    ):
        self._skills_dir = Path(skills_dir or _DEFAULT_PY_SKILLS_DIR)
        self._ext_skills_dir = Path(ext_skills_dir or _DEFAULT_EXT_SKILLS_DIR)
        self._discovery_roots = [Path(p) for p in (discovery_roots or _default_discovery_roots())]

        self._skills_dir.mkdir(exist_ok=True)
        self._ext_skills_dir.mkdir(exist_ok=True)

        self._lock = threading.Lock()
        self._skills: dict[str, object] = {}          # manager_skill_name -> module/adapter
        self._tool_index: dict[str, str] = {}         # tool_name -> manager_skill_name
        self._skill_meta: dict[str, dict] = {}        # manager_skill_name -> metadata
        self._skill_paths: dict[str, Path] = {}       # manager_skill_name -> source path
        self._skill_kinds: dict[str, str] = {}        # python | skillmd
        self._skill_managed: dict[str, bool] = {}     # removable by this manager

        self._load_all()

    # ------------------------------------------------------------------ load

    def _load_all(self):
        seen_skillmd_paths: set[str] = set()

        for f in sorted(self._skills_dir.glob("*.py")):
            if not f.name.startswith("_"):
                self._load_file(f)

        for d in sorted(self._ext_skills_dir.iterdir()) if self._ext_skills_dir.exists() else []:
            if d.is_dir() and (d / "SKILL.md").exists():
                if self._load_skill_dir(d, managed=True):
                    seen_skillmd_paths.add(str(d.resolve()).lower())

        for root in self._discovery_roots:
            if not root.exists():
                continue
            for d in _iter_candidate_skillmd_dirs(root):
                key = str(d.resolve()).lower()
                if key in seen_skillmd_paths:
                    continue
                self._load_skill_dir(d, managed=False)
                seen_skillmd_paths.add(key)

    def _register_skill(self, base_name: str, mod: object, *, path: Path, kind: str, managed: bool) -> str:
        meta = getattr(mod, "META", {}) or {}
        desired = _safe_slug(meta.get("name") or base_name, lower=False, max_len=64)

        with self._lock:
            # Ensure manager key uniqueness.
            name = desired
            if name in self._skills:
                i = 2
                while f"{desired}_{i}" in self._skills:
                    i += 1
                name = f"{desired}_{i}"

            self._skills[name] = mod
            self._skill_meta[name] = dict(meta)
            self._skill_paths[name] = path
            self._skill_kinds[name] = kind
            self._skill_managed[name] = managed

            for t in getattr(mod, "TOOLS", []):
                try:
                    tool_name = t["function"]["name"]
                except Exception:
                    continue
                old_owner = self._tool_index.get(tool_name)
                if old_owner and old_owner != name:
                    log.warning("Tool name collision: %s (%s -> %s)", tool_name, old_owner, name)
                self._tool_index[tool_name] = name

        return name

    def _load_file(self, path: Path) -> bool:
        try:
            spec = importlib.util.spec_from_file_location(f"starbot_skill_{path.stem}", path)
            if spec is None or spec.loader is None:
                raise RuntimeError("invalid module spec")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if not hasattr(mod, "TOOLS") or not hasattr(mod, "execute"):
                log.warning("Skill %s skipped: missing TOOLS or execute()", path.name)
                return False

            meta = getattr(mod, "META", {}) or {}
            manager_name = self._register_skill(meta.get("name", path.stem), mod, path=path, kind="python", managed=True)
            log.info("Skill loaded: %s v%s (%d tool(s))", manager_name, meta.get("version", "?"), len(getattr(mod, "TOOLS", [])))
            return True
        except Exception as e:
            log.error("Failed to load skill %s: %s", path.name, e)
            return False

    def _make_unique_tool_name(self, base_slug: str) -> str:
        base = f"skillmd_{_safe_slug(base_slug, lower=True, max_len=48)}"
        name = base[:64]
        with self._lock:
            if name not in self._tool_index:
                return name
            i = 2
            while True:
                suffix = f"_{i}"
                cand = (base[: max(1, 64 - len(suffix))] + suffix)
                if cand not in self._tool_index:
                    return cand
                i += 1

    def _load_skill_dir(self, path: Path, managed: bool) -> bool:
        skill_md = path / "SKILL.md"
        if not skill_md.exists():
            return False
        try:
            text = _read_text(skill_md)
            meta = _parse_skillmd_meta(text, path.name)
            meta.setdefault("name", path.name)
            meta.setdefault("version", "skillmd")
            meta.setdefault("author", "")
            meta.setdefault("description", "External SKILL.md skill")

            tool_name = self._make_unique_tool_name(str(meta.get("name", path.name)))
            adapter = _MarkdownSkillAdapter(path, meta, tool_name)
            manager_name = self._register_skill(
                str(meta.get("name", path.name)),
                adapter,
                path=path,
                kind="skillmd",
                managed=managed,
            )
            log.info("SKILL.md loaded: %s (%s)", manager_name, path)
            return True
        except Exception as e:
            log.error("Failed to load SKILL.md skill %s: %s", path, e)
            return False

    def reload(self):
        """Unload all skills and reload from disk."""
        with self._lock:
            self._skills.clear()
            self._tool_index.clear()
            self._skill_meta.clear()
            self._skill_paths.clear()
            self._skill_kinds.clear()
            self._skill_managed.clear()
        self._load_all()

    # --------------------------------------------------------------- install

    def install(self, source: str) -> tuple[bool, str]:
        """Install a skill from local/remote sources.

        Supported sources:
        - Native python skill file (.py) URL/path (legacy)
        - Local SKILL.md directory
        - Local .zip containing SKILL.md
        - Remote .zip containing SKILL.md
        - GitHub repo/tree URL containing SKILL.md
        - skillsmp.com page URL (resolves GitHub repo link)
        """
        source = (source or "").strip()
        if not source:
            return False, "空来源"

        try:
            # 1) Direct local directory / SKILL.md
            local = Path(source)
            if local.exists():
                if local.is_dir() and (local / "SKILL.md").exists():
                    return self._install_skillmd_dir(local)
                if local.is_file() and local.name.upper() == "SKILL.MD":
                    return self._install_skillmd_dir(local.parent)
                if local.is_file() and local.suffix.lower() == ".zip":
                    return self._install_skillmd_zip_path(local)
                if local.is_file() and local.suffix.lower() == ".py":
                    return self._install_python_from_text(local.read_text(encoding="utf-8"), local.stem)

            # 2) skillsmp page -> resolve GitHub repo and install as SKILL.md
            if "skillsmp.com" in source:
                return self._install_from_skillsmp(source)

            # 3) GitHub repo/tree URL -> prefer SKILL.md install, fallback to python
            gh = _parse_github_tree_url(source)
            if gh and not source.endswith(".py"):
                ok, msg = self._install_skillmd_from_github(source)
                if ok:
                    return ok, msg
                # fallback to legacy python repo flow

            # 4) Remote zip
            if source.lower().startswith("http") and source.lower().endswith(".zip"):
                return self._install_skillmd_zip_url(source)

            # 5) Raw remote/local SKILL.md (single-file skill)
            if source.lower().endswith("/skill.md") or source.lower().endswith("\\skill.md") or source.lower().endswith(".md"):
                try:
                    text = self._fetch_text_source(source)
                except Exception:
                    text = ""
                if "SKILL" in source.upper() and text.strip():
                    return self._install_skillmd_single_file_text(text, source)

            # 6) Legacy Python plugin path/URL
            text = self._fetch_text_source(source)
            return self._install_python_from_text(text, Path(urlparse(source).path or source).stem)
        except Exception as e:
            return False, f"安装失败: {e}"

    def _install_python_from_text(self, content: str, source_stem: str) -> tuple[bool, str]:
        if not content:
            return False, "内容为空"
        if "def execute" not in content or "TOOLS" not in content:
            return False, "不是受支持的 Python skill（需要包含 TOOLS 和 execute）"

        m = re.search(r'"name"\s*:\s*"([^"]+)"', content)
        raw_name = m.group(1) if m else source_stem
        skill_name = _safe_slug(raw_name, lower=False, max_len=64)
        dest = self._skills_dir / f"{skill_name}.py"
        dest.write_text(content, encoding="utf-8")

        if self._load_file(dest):
            return True, f"已安装 Python skill `{skill_name}`"
        dest.unlink(missing_ok=True)
        return False, "文件已保存但加载失败，请检查格式"

    def _fetch_text_source(self, source: str) -> str:
        if not source.startswith("http"):
            return Path(source).read_text(encoding="utf-8")

        # Legacy GitHub repo python plugin auto-find
        if "github.com" in source and not source.endswith(".py"):
            raw_base = source.rstrip("/").replace("https://github.com/", "https://raw.githubusercontent.com/")
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
            raise ValueError("在 GitHub 仓库根目录未找到 skill.py / main.py")

        r = requests.get(source, timeout=15)
        r.raise_for_status()
        return r.text

    def _install_skillmd_single_file_text(self, text: str, source: str) -> tuple[bool, str]:
        parsed = _parse_skillmd_meta(text, Path(urlparse(source).path or source).stem or "skillmd")
        dest_name = _safe_slug(parsed.get("name", "skillmd"))
        dest = self._unique_install_dir(dest_name)
        dest.mkdir(parents=True, exist_ok=False)
        (dest / "SKILL.md").write_text(text, encoding="utf-8")
        if self._load_skill_dir(dest, managed=True):
            return True, f"已安装 SKILL.md skill `{parsed.get('name', dest.name)}`（单文件）"
        shutil.rmtree(dest, ignore_errors=True)
        return False, "SKILL.md 已保存但加载失败"

    def _unique_install_dir(self, base_slug: str) -> Path:
        slug = _safe_slug(base_slug)
        dest = self._ext_skills_dir / slug
        if not dest.exists():
            return dest
        i = 2
        while True:
            cand = self._ext_skills_dir / f"{slug}_{i}"
            if not cand.exists():
                return cand
            i += 1

    def _install_skillmd_dir(self, src_dir: Path) -> tuple[bool, str]:
        src_dir = src_dir.resolve()
        skill_md = src_dir / "SKILL.md"
        if not skill_md.exists():
            return False, "目录中未找到 SKILL.md"

        meta = _parse_skillmd_meta(_read_text(skill_md), src_dir.name)
        dest = self._unique_install_dir(str(meta.get("name", src_dir.name)))

        def _ignore(_d, names):
            ignored = {n for n in names if n in {".git", "__pycache__"}}
            return ignored

        shutil.copytree(src_dir, dest, ignore=_ignore)
        if self._load_skill_dir(dest, managed=True):
            return True, f"已安装 SKILL.md skill `{meta.get('name', dest.name)}`"

        shutil.rmtree(dest, ignore_errors=True)
        return False, "目录已复制但加载失败"

    def _install_skillmd_zip_path(self, zip_path: Path) -> tuple[bool, str]:
        data = zip_path.read_bytes()
        return self._install_skillmd_from_zip_bytes(data, source_label=str(zip_path))

    def _install_skillmd_zip_url(self, url: str) -> tuple[bool, str]:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return self._install_skillmd_from_zip_bytes(r.content, source_label=url)

    def _install_skillmd_from_zip_bytes(self, data: bytes, source_label: str) -> tuple[bool, str]:
        with TemporaryDirectory() as td:
            root = Path(td)
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(root)
            candidates = _iter_candidate_skillmd_dirs(root)
            chosen, all_candidates = _pick_skillmd_dir(candidates)
            if chosen is None:
                return False, f"压缩包中未找到 SKILL.md（{source_label}）"
            ok, msg = self._install_skillmd_dir(chosen)
            if ok and len(all_candidates) > 1:
                msg += f"（检测到 {len(all_candidates)} 个 SKILL.md，已选择最浅层目录）"
            return ok, msg

    def _install_from_skillsmp(self, url: str) -> tuple[bool, str]:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        html = r.text

        # Prefer tree URL if present; fallback to repo root URL.
        matches = re.findall(
            r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/tree/[A-Za-z0-9_.\-/]+)?",
            html,
        )
        if not matches:
            return False, "无法从 skillsmp 页面解析 GitHub 仓库链接"

        # Try tree links first (more precise than repo root).
        matches.sort(key=lambda u: ("/tree/" not in u, len(u)))
        for m in matches:
            ok, msg = self._install_skillmd_from_github(m)
            if ok:
                return True, f"{msg}（来源 skillsmp）"
        return False, "skillsmp 页面已解析到 GitHub 链接，但安装失败"

    def _install_skillmd_from_github(self, url: str) -> tuple[bool, str]:
        parsed = _parse_github_tree_url(url)
        if not parsed:
            return False, "不是支持的 GitHub repo/tree URL"
        owner, repo, branch_hint, subpath = parsed

        last_err: Exception | None = None
        for zip_url in _github_repo_zip_urls(owner, repo, branch_hint):
            try:
                r = requests.get(zip_url, timeout=25)
                r.raise_for_status()
            except Exception as e:
                last_err = e
                continue

            with TemporaryDirectory() as td:
                root = Path(td)
                with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                    zf.extractall(root)

                top_dirs = [p for p in root.iterdir() if p.is_dir()]
                repo_root = top_dirs[0] if len(top_dirs) == 1 else root

                if subpath:
                    candidate = repo_root / Path(subpath.replace("/", "\\"))
                    if (candidate / "SKILL.md").exists():
                        return self._install_skillmd_dir(candidate)
                    return False, f"GitHub tree 子路径未找到 SKILL.md: {subpath}"

                candidates = _iter_candidate_skillmd_dirs(repo_root)
                chosen, all_candidates = _pick_skillmd_dir(candidates)
                if chosen is None:
                    last_err = ValueError("repo zip 中未找到 SKILL.md")
                    continue
                ok, msg = self._install_skillmd_dir(chosen)
                if ok and len(all_candidates) > 1:
                    msg += f"（仓库中有 {len(all_candidates)} 个 SKILL.md，已选最浅层）"
                return ok, msg

        return False, f"从 GitHub 安装 SKILL.md 失败: {last_err or 'unknown error'}"

    # ---------------------------------------------------------------- remove

    def remove(self, name: str) -> tuple[bool, str]:
        """Uninstall a managed skill by its displayed/manager name."""
        target_key: str | None = None
        target_path: Path | None = None

        with self._lock:
            for key, meta in self._skill_meta.items():
                display = str(meta.get("name", key))
                if key == name or display == name:
                    target_key = key
                    target_path = self._skill_paths.get(key)
                    break

        if target_key is None:
            return False, f"未找到 skill: `{name}`"

        managed = self._skill_managed.get(target_key, False)
        if not managed:
            p = self._skill_paths.get(target_key)
            return False, f"该 skill 为外部发现项，请在原位置删除：`{p}`"

        with self._lock:
            mod = self._skills.pop(target_key, None)
            self._skill_meta.pop(target_key, None)
            self._skill_kinds.pop(target_key, None)
            self._skill_managed.pop(target_key, None)
            self._skill_paths.pop(target_key, None)
            if mod:
                tool_names = [
                    t.get("function", {}).get("name")
                    for t in getattr(mod, "TOOLS", [])
                    if isinstance(t, dict)
                ]
                for tn in tool_names:
                    if tn and self._tool_index.get(tn) == target_key:
                        self._tool_index.pop(tn, None)

        if target_path:
            try:
                if target_path.is_dir():
                    shutil.rmtree(target_path)
                elif target_path.is_file():
                    target_path.unlink(missing_ok=True)
            except Exception as e:
                return False, f"已从内存卸载，但删除文件失败: {e}"

        return True, f"已删除 skill `{name}`"

    # ---------------------------------------------------------------- route

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

    # ---------------------------------------------------------------- query

    @property
    def tools_schema(self) -> list[dict]:
        with self._lock:
            schema: list[dict] = []
            for mod in self._skills.values():
                schema.extend(getattr(mod, "TOOLS", []))
            return schema

    def list_skills(self) -> list[dict]:
        with self._lock:
            out: list[dict] = []
            for key, mod in self._skills.items():
                meta = self._skill_meta.get(key, getattr(mod, "META", {}) or {})
                out.append({
                    "name": meta.get("name", key),
                    "version": meta.get("version", "?"),
                    "description": meta.get("description", ""),
                    "author": meta.get("author", ""),
                    "tools": [t.get("function", {}).get("name", "") for t in getattr(mod, "TOOLS", [])],
                    "kind": self._skill_kinds.get(key, "python"),
                    "managed": self._skill_managed.get(key, False),
                    "path": str(self._skill_paths.get(key, "")),
                    "id": key,
                })
            out.sort(key=lambda x: (str(x.get("name", "")).lower(), str(x.get("id", "")).lower()))
            return out
