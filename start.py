from __future__ import annotations

import glob
import io
import os
import shutil
import subprocess
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))


# Core Python dependencies: (import_name, pip_install_spec)
CORE_DEPS = [
    ("anthropic", "anthropic[vertex]>=0.82.0"),
    ("pyautogui", "pyautogui>=0.9.54"),
    ("pyperclip", "pyperclip>=1.9.0"),
    ("PIL", "pillow>=12.1.1"),
    ("dotenv", "python-dotenv>=1.2.1"),
    ("requests", "requests>=2.32.5"),
    ("apscheduler", "apscheduler>=3.11.2"),
    ("pydantic_ai", "pydantic-ai>=1.62.0"),
    ("discord", "discord.py>=2.6.4"),
    ("psutil", "psutil>=7.2.2"),
    ("openai", "openai>=2.21.0"),
    ("prompt_toolkit", "prompt-toolkit>=3.0.0"),
    ("yt_dlp", "yt-dlp>=2024.0.0"),
    ("pytesseract", "pytesseract>=0.3.10"),
    ("trafilatura", "trafilatura>=1.6.0"),
    ("qrcode", "qrcode[pil]>=8.2"),
    ("playwright", "playwright>=1.58.0"),
    ("faster_whisper", "faster-whisper>=1.2.1"),
]

# Skill-specific dependencies: skill file name -> [(import_name, pip_spec), ...]
SKILL_DEPS: dict[str, list[tuple[str, str]]] = {
    "qrcode_skill": [("qrcode", "qrcode[pil]>=8.2")],
    "browser_agent": [("playwright", "playwright>=1.58.0")],
    "video_learn": [
        ("faster_whisper", "faster-whisper>=1.2.1"),
        ("yt_dlp", "yt-dlp>=2024.0.0"),
    ],
    "monitor": [("requests", "requests>=2.32.5")],
    "stock": [("requests", "requests>=2.32.5")],
    "translate": [("requests", "requests>=2.32.5")],
    "news": [("requests", "requests>=2.32.5")],
    "smart_search": [
        ("requests", "requests>=2.32.5"),
        ("trafilatura", "trafilatura>=1.6.0"),
    ],
    "sysmon": [("psutil", "psutil>=7.2.2")],
}

REQUIRED_DIRS = [
    "logs",
    "logs/frames",
    "logs/subs",
    "logs/video_learn",
    "skills",
]


def print_banner() -> None:
    """Print a simple startup banner."""
    if sys.platform == "win32":
        # Enable ANSI colors in Windows console where supported.
        os.system("")

    r = "\033[0m"
    b = "\033[94m"
    c = "\033[96m"
    g = "\033[90m"

    print()
    print(f"{b}Starbot{r} {g}|{r} {c}Discord-controlled desktop AI agent{r}")
    print(f"{g}ReAct + tools + memory + skills{r}")
    print()


def _installer() -> list[str]:
    """Return the installer command prefix (uv pip install or pip install)."""
    if shutil.which("uv"):
        return ["uv", "pip", "install"]
    return [sys.executable, "-m", "pip", "install"]


def _can_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _pip_install(packages: list[str]) -> bool:
    """Install pip packages and return whether the install succeeded."""
    if not packages:
        return True
    cmds: list[list[str]] = []
    uv_path = shutil.which("uv")
    if uv_path:
        cmds.append(["uv", "pip", "install"] + packages)
    cmds.append([sys.executable, "-m", "pip", "install"] + packages)

    last_err_text = ""
    for idx, cmd in enumerate(cmds):
        label = "uv" if cmd and cmd[0].lower() == "uv" else "pip"
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as e:
            if idx < len(cmds) - 1:
                if getattr(e, "winerror", None) == 4551:
                    print(f"  warning: {label} is blocked by application control policy, falling back...")
                else:
                    print(f"  warning: failed to launch {label} installer ({e}), falling back...")
                continue
            last_err_text = str(e)
            break

        if r.returncode == 0:
            return True

        last_err_text = (r.stderr or r.stdout or "").strip()[:800]
        if idx < len(cmds) - 1:
            print(f"  warning: {label} install failed, trying fallback installer...")
            continue

    print(f"  ERROR install failed:\n{last_err_text}")
    return False


def _ensure_bootstrap_deps_for_config() -> bool:
    """
    Ensure minimal dependencies needed to import config/setup before full checks.

    `config.py` imports `python-dotenv` at module import time, so setup-related CLI
    modes need it available before we can even enter the configuration wizard.
    """
    if _can_import("dotenv"):
        return True

    print("  Missing bootstrap dependency: python-dotenv")
    print("  Installing python-dotenv so the configuration wizard can start...")
    ok = _pip_install(["python-dotenv>=1.2.1"])
    if ok:
        print("  OK  python-dotenv installed\n")
    else:
        print("  ERROR Failed to install python-dotenv; cannot start configuration wizard.\n")
    return ok


def install_core_deps() -> bool:
    """[1/5] Check and install core Python dependencies."""
    print("[1/5] Core Python dependencies")
    missing: list[str] = []
    for import_name, pkg in CORE_DEPS:
        if _can_import(import_name):
            print(f"  OK  {import_name}")
        else:
            print(f"  MISS {import_name} -> {pkg}")
            missing.append(pkg)

    if not missing:
        print("  Ready\n")
        return True

    print(f"\n  Installing {len(missing)} missing packages...")
    if not _pip_install(missing):
        return False
    print("  Installed\n")
    return True


def install_playwright_browser() -> None:
    """[2/5] Ensure Playwright Chromium is installed."""
    print("[2/5] Playwright Chromium")

    if not _can_import("playwright"):
        print("  warning: playwright not installed, skipping browser install (browser_agent may be unavailable)\n")
        return

    install_cmds = [
        ["playwright", "install", "chromium"],
        [sys.executable, "-m", "playwright", "install", "chromium"],
    ]
    installed = False
    for cmd in install_cmds:
        if cmd[0] == sys.executable or shutil.which(cmd[0]):
            print("  Checking Chromium install (first run may download ~130MB)...")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                print("  OK  Chromium ready\n")
                installed = True
                break

    if not installed:
        print("  warning: Chromium install failed, run manually: playwright install chromium\n")


def check_external_tools() -> None:
    """[3/5] Check recommended external tools (yt-dlp, tesseract)."""
    print("[3/5] External tools")

    if shutil.which("yt-dlp"):
        r = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        print(f"  OK  yt-dlp {r.stdout.strip()}")
    else:
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            print(f"  OK  yt-dlp (module) {r.stdout.strip()}")
        else:
            print("  warning: yt-dlp not available (video/audio download features may be limited)")

    if shutil.which("tesseract"):
        r = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
        ver = (r.stdout or r.stderr).splitlines()[0] if (r.stdout or r.stderr) else "?"
        print(f"  OK  Tesseract OCR: {ver}")
    else:
        print("  warning: Tesseract OCR not installed (optional, used for OCR)")
        print("    Download: https://github.com/UB-Mannheim/tesseract/wiki")

    print()


def check_skill_deps() -> bool:
    """[4/5] Scan skills/ and install missing optional dependencies."""
    print("[4/5] Skill dependencies")

    skills_dir = os.path.join(_DIR, "skills")
    if not os.path.isdir(skills_dir):
        print("  (skills/ not found, skipped)\n")
        return True

    skill_files = sorted(glob.glob(os.path.join(skills_dir, "*.py")))
    if not skill_files:
        print("  (no skill files, skipped)\n")
        return True

    all_missing: list[str] = []
    for skill_path in skill_files:
        name = os.path.splitext(os.path.basename(skill_path))[0]
        if name.startswith("_") or name == "example":
            continue
        deps = SKILL_DEPS.get(name, [])
        bad = [pkg for imp, pkg in deps if not _can_import(imp)]
        if bad:
            print(f"  MISS {name}: {', '.join(bad)}")
            all_missing.extend(bad)
        else:
            print(f"  OK  {name}")

    if all_missing:
        seen: set[str] = set()
        unique: list[str] = []
        for p in all_missing:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        print(f"\n  Installing skill dependencies: {', '.join(unique)}")
        if not _pip_install(unique):
            print("  warning: some skill dependencies failed to install; related skills may be unavailable")
        else:
            print("  Installed skill dependencies")
    else:
        print("  Ready")

    print()
    return True


def check_dirs() -> None:
    """[5/5] Ensure required directories exist."""
    print("[5/5] Initialize directories")
    for d in REQUIRED_DIRS:
        path = os.path.join(_DIR, d)
        os.makedirs(path, exist_ok=True)
        print(f"  OK  {d}/")
    print()


def check_api() -> bool:
    """Validate LLM API config and connectivity."""
    from config import config

    if not config.LLM_API_BASE or not config.LLM_API_KEY:
        print("  ERROR LLM API not configured (.env)")
        return False

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_API_BASE,
            timeout=10,
        )
        client.models.list()
        print(f"  OK  LLM API reachable ({config.LLM_API_BASE})")
    except Exception as e:
        # Keep startup behavior lenient: warn, but do not block startup.
        print(f"  warning: LLM API connectivity check failed: {e}")
        print("  Startup will continue, but AI features may not work until the API is reachable.")
    return True


def check_discord() -> bool:
    """Validate required Discord config."""
    from config import config

    if not config.DISCORD_BOT_TOKEN:
        print("  ERROR Discord Bot Token not configured (.env)")
        return False
    if not config.DISCORD_CHANNEL_ID:
        print("  ERROR Discord default notify channel ID not configured (.env)")
        return False
    print(f"  OK  Discord config ready (default notify channel: {config.DISCORD_CHANNEL_ID})")
    return True


class _Tee:
    """Mirror stdout to terminal and an in-memory buffer while counting lines."""

    def __init__(self, real):
        self._real = real
        self._buf = io.StringIO()
        self.lines = 0

    def write(self, text):
        self._real.write(text)
        self._buf.write(text)
        self.lines += text.count("\n")

    def flush(self):
        self._real.flush()

    def getvalue(self):
        return self._buf.getvalue()


def _run_section(title: str, fn, *args, **kwargs):
    """
    Run a startup section and collapse successful multi-line output into one line.

    Sections with failures or warnings stay expanded so the user can read details.
    """

    blue = "\033[94m"
    gray = "\033[90m"
    reset = "\033[0m"

    tee = _Tee(sys.stdout)
    sys.stdout = tee
    try:
        result = fn(*args, **kwargs)
    finally:
        sys.stdout = tee._real

    output = tee.getvalue()
    n_lines = tee.lines
    has_warning = ("warning" in output.lower()) or ("⚠" in output)
    failed = (result is False) or ("ERROR" in output) or ("❌" in output)

    if not failed and not has_warning and n_lines > 1:
        sys.stdout.write(f"\033[{n_lines}A\033[J")
        sys.stdout.write(f"  {blue}OK{reset}  {gray}{title}{reset}\n")
        sys.stdout.flush()

    return result


def _parse_start_cli(argv: list[str]) -> dict[str, bool]:
    """Minimal CLI flags for startup/setup workflows."""
    opts = {"force_setup": False, "setup_only": False}
    for raw in argv:
        arg = (raw or "").strip().lower()
        if arg in {"setup", "config"}:
            opts["force_setup"] = True
            opts["setup_only"] = True
        elif arg in {"--setup", "--config", "--wizard"}:
            opts["force_setup"] = True
        elif arg in {"--setup-only", "--config-only", "--wizard-only"}:
            opts["force_setup"] = True
            opts["setup_only"] = True
    return opts


def main():
    os.chdir(_DIR)
    cli = _parse_start_cli(sys.argv[1:])

    print_banner()

    reset = "\033[0m"
    blue = "\033[94m"
    white = "\033[97m"
    cyan = "\033[96m"

    def _launch(title: str) -> None:
        bar = "=" * 62
        print(f"\n  {blue}{bar}{reset}")
        print(f"  {cyan}  * {white}{title}{cyan} *{reset}")
        print(f"  {blue}{bar}{reset}\n")

    print(f"  {blue}>>{white} Startup checks{reset}\n")

    if not _ensure_bootstrap_deps_for_config():
        input("\nPress Enter to exit...")
        sys.exit(1)

    from config import setup

    if cli["setup_only"]:
        print("  Running configuration wizard only (no startup checks).")
        print("  Tip: 'Skip / Modify' choices appear for steps that are already fully configured.\n")
        setup(force=True)
        return

    if cli["force_setup"]:
        _run_section("Configuration wizard (reconfigure)", setup, True)
    else:
        _run_section("Configuration wizard", setup)

    if not _run_section("Core Python dependencies", install_core_deps):
        input("\nPress Enter to exit...")
        sys.exit(1)

    _run_section("Playwright Chromium", install_playwright_browser)
    _run_section("External tools", check_external_tools)
    _run_section("Skill dependencies", check_skill_deps)
    _run_section("Initialize directories", check_dirs)

    if not _run_section("LLM API connectivity", check_api):
        input("\nPress Enter to exit...")
        sys.exit(1)
    if not _run_section("Discord configuration", check_discord):
        input("\nPress Enter to exit...")
        sys.exit(1)

    _launch("Starbot is connecting to Discord...")
    from comms.discord_client import start_discord

    start_discord()


if __name__ == "__main__":
    main()
