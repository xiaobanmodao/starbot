import io
import os
import sys
import subprocess
import shutil
import glob

_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────
# 核心 Python 依赖  (import_name, pip_install_spec)
# ─────────────────────────────────────────────────────────────────
CORE_DEPS = [
    ("anthropic",      "anthropic[vertex]>=0.82.0"),
    ("pyautogui",      "pyautogui>=0.9.54"),
    ("pyperclip",      "pyperclip>=1.9.0"),
    ("PIL",            "pillow>=12.1.1"),
    ("dotenv",         "python-dotenv>=1.2.1"),
    ("requests",       "requests>=2.32.5"),
    ("apscheduler",    "apscheduler>=3.11.2"),
    ("pydantic_ai",    "pydantic-ai>=1.62.0"),
    ("discord",        "discord.py>=2.6.4"),
    ("psutil",         "psutil>=7.2.2"),
    ("openai",         "openai>=2.21.0"),
    ("prompt_toolkit", "prompt_toolkit>=3.0.0"),
    ("yt_dlp",         "yt-dlp>=2024.0.0"),
    ("pytesseract",    "pytesseract>=0.3.10"),
    ("trafilatura",    "trafilatura>=1.6.0"),
    ("qrcode",         "qrcode[pil]>=8.2"),
    ("playwright",     "playwright>=1.58.0"),
    ("faster_whisper", "faster-whisper>=1.2.1"),
]

# Skill 专属依赖 (skill 文件名 → [(import_name, pip_spec), ...])
SKILL_DEPS: dict = {
    "qrcode_skill":  [("qrcode",         "qrcode[pil]>=8.2")],
    "browser_agent": [("playwright",      "playwright>=1.58.0")],
    "video_learn":   [("faster_whisper",  "faster-whisper>=1.2.1"),
                      ("yt_dlp",          "yt-dlp>=2024.0.0")],
    "monitor":       [("requests",        "requests>=2.32.5")],
    "stock":         [("requests",        "requests>=2.32.5")],
    "translate":     [("requests",        "requests>=2.32.5")],
    "news":          [("requests",        "requests>=2.32.5")],
    "smart_search":  [("requests",        "requests>=2.32.5"),
                      ("trafilatura",     "trafilatura>=1.6.0")],
    "sysmon":        [("psutil",          "psutil>=7.2.2")],
}

# 目录列表（相对项目根）
REQUIRED_DIRS = [
    "logs",
    "logs/frames",
    "logs/subs",
    "logs/video_learn",
    "skills",
]


# ─────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────

def print_banner() -> None:
    """打印 Starbot 星空风格 ASCII 艺术 Banner。"""
    if sys.platform == "win32":
        os.system("")  # 激活 Windows 控制台 ANSI/VT100 支持

    R = "\033[0m"   # Reset
    B = "\033[94m"  # Bright Blue
    W = "\033[97m"  # Bright White
    C = "\033[96m"  # Bright Cyan
    G = "\033[90m"  # Dark Gray

    stars_a = (
        f"  {C}✦{G}· {R}  {B}✦{R}   {G}·{R}  {C}✦{R}   {G}·{R}  "
        f"{B}✦{R}   {G}·{R}   {C}✦{R}  {G}·{R}  {B}✦{R}   {G}·{R}  "
        f"{C}✦{R}  {G}·{R}  {B}✦{G}·{R}"
    )
    stars_b = (
        f"  {G}·{R}  {B}✦{R}   {G}·{R}    {C}✦{R}   {G}·{R}  "
        f"{B}✦{R}    {G}·{R}   {C}✦{R}  {G}·{R}    {B}✦{R}   "
        f"{G}·{R}  {C}✦{G}·{R}  {B}✦{R}"
    )

    # ANSI Shadow 字体风格，蓝白交替渐变
    logo = [
        f"  {B}███████╗{W}████████╗{B} █████╗ {W}██████╗ {B}██████╗  {W}██████╗ {B}████████╗{R}",
        f"  {B}██╔════╝{W}╚══██╔══╝{B}██╔══██╗{W}██╔══██╗{B}██╔══██╗{W}██╔═══██╗{B}╚══██╔══╝{R}",
        f"  {W}███████╗{B}   ██║   {W}███████║{B}██████╔╝{W}██████╔╝{B}██║   ██║{W}   ██║   {R}",
        f"  {B}╚════██║{W}   ██║   {B}██╔══██║{W}██╔══██╗{B}██╔══██╗{W}██║   ██║{B}   ██║   {R}",
        f"  {W}███████║{B}   ██║   {W}██║  ██║{B}██║  ██║{W}██████╔╝{B}╚██████╔╝{W}   ██║   {R}",
        f"  {B}╚══════╝{W}   ╚═╝   {B}╚═╝  ╚═╝{W}╚═╝  ╚═╝{B}╚═════╝ {W} ╚═════╝ {B}   ╚═╝   {R}",
    ]

    div = f"  {B}{'─' * 64}{R}"

    print()
    print(stars_a)
    print()
    for line in logo:
        print(line)
    print()
    print(f"  {C}✦  AI 驱动的 Windows 桌面自动化助手  ·  v0.1.0  ✦{R}")
    print(f"  {G}Discord · ReAct 推理引擎 · 50+ 工具 · OpenAI / Claude / DeepSeek{R}")
    print()
    print(div)
    print()
    print(stars_b)
    print()


# ─────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────

def _installer() -> list:
    """返回安装命令前缀：uv pip install 或 pip install。"""
    if shutil.which("uv"):
        return ["uv", "pip", "install"]
    return [sys.executable, "-m", "pip", "install"]


def _can_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _pip_install(packages: list) -> bool:
    """安装若干 pip 包，返回是否全部成功。"""
    if not packages:
        return True
    cmd = _installer() + packages
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ❌ 安装失败:\n{r.stderr[:600]}")
        return False
    return True


# ─────────────────────────────────────────────────────────────────
# 检查步骤
# ─────────────────────────────────────────────────────────────────

def install_core_deps() -> bool:
    """[1/5] 检查并安装所有核心 Python 依赖。"""
    print("[1/5] 核心 Python 依赖")
    missing = []
    for import_name, pkg in CORE_DEPS:
        if _can_import(import_name):
            print(f"  ✓ {import_name}")
        else:
            print(f"  ✗ {import_name}  →  待安装 {pkg}")
            missing.append(pkg)

    if not missing:
        print("  → 全部就绪\n")
        return True

    print(f"\n  正在安装 {len(missing)} 个缺失包...")
    if not _pip_install(missing):
        return False
    print("  → 安装完成\n")
    return True


def install_playwright_browser() -> None:
    """[2/5] 确保 Playwright Chromium 浏览器已下载。"""
    print("[2/5] Playwright Chromium 浏览器")

    if not _can_import("playwright"):
        print("  ⚠ playwright 未安装，跳过（browser_agent 技能将不可用）\n")
        return

    # 尝试通过 playwright CLI 安装 chromium（已装则秒完成）
    install_cmds = [
        ["playwright", "install", "chromium"],
        [sys.executable, "-m", "playwright", "install", "chromium"],
    ]
    installed = False
    for cmd in install_cmds:
        if cmd[0] == sys.executable or shutil.which(cmd[0]):
            print("  正在确认 Chromium 已安装（首次下载约 130 MB）...")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                print("  ✓ Chromium 就绪\n")
                installed = True
                break

    if not installed:
        print("  ⚠ Chromium 安装失败，请手动运行: playwright install chromium\n")


def check_external_tools() -> None:
    """[3/5] 检查外部命令行工具（yt-dlp、Tesseract）。"""
    print("[3/5] 外部工具")

    # yt-dlp：优先 PATH，其次模块调用
    if shutil.which("yt-dlp"):
        r = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        ver = r.stdout.strip()
        print(f"  ✓ yt-dlp {ver}")
    else:
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            print(f"  ✓ yt-dlp (模块) {r.stdout.strip()}")
        else:
            print("  ⚠ yt-dlp 不可用，视频/音频下载功能受限")

    # Tesseract OCR（可选）
    if shutil.which("tesseract"):
        r = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
        ver = (r.stdout or r.stderr).splitlines()[0] if r.stdout or r.stderr else "?"
        print(f"  ✓ Tesseract OCR: {ver}")
    else:
        print("  ⚠ Tesseract OCR 未安装（可选，用于截图文字识别）")
        print("    下载地址: https://github.com/UB-Mannheim/tesseract/wiki")

    print()


def check_skill_deps() -> bool:
    """[4/5] 扫描 skills/ 并安装各技能所需依赖。"""
    print("[4/5] Skill 技能依赖")

    skills_dir = os.path.join(_DIR, "skills")
    if not os.path.isdir(skills_dir):
        print("  (skills/ 目录不存在，跳过)\n")
        return True

    skill_files = sorted(glob.glob(os.path.join(skills_dir, "*.py")))
    if not skill_files:
        print("  (无技能文件，跳过)\n")
        return True

    all_missing: list = []
    for skill_path in skill_files:
        name = os.path.splitext(os.path.basename(skill_path))[0]
        if name.startswith("_") or name == "example":
            continue

        deps = SKILL_DEPS.get(name, [])
        bad = [pkg for imp, pkg in deps if not _can_import(imp)]
        if bad:
            print(f"  ✗ {name}: 缺少 {', '.join(bad)}")
            all_missing.extend(bad)
        else:
            print(f"  ✓ {name}")

    if all_missing:
        # 去重保序
        seen: set = set()
        unique: list = []
        for p in all_missing:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        print(f"\n  正在安装 skill 依赖: {', '.join(unique)}")
        if not _pip_install(unique):
            print("  ⚠ 部分 skill 依赖安装失败，相关技能可能不可用")
        else:
            print("  → Skill 依赖安装完成")
    else:
        print("  → 全部就绪")

    print()
    return True


def check_dirs() -> None:
    """[5/5] 确保必要目录存在。"""
    print("[5/5] 初始化目录")
    for d in REQUIRED_DIRS:
        path = os.path.join(_DIR, d)
        os.makedirs(path, exist_ok=True)
        print(f"  ✓ {d}/")
    print()


def check_api() -> bool:
    """验证 LLM API 连通性。"""
    from config import config
    if not config.LLM_API_BASE or not config.LLM_API_KEY:
        print("  ❌ LLM API 未配置（请检查 .env）")
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_API_BASE, timeout=10)
        client.models.list()
        print(f"  ✓ LLM API 连接正常 ({config.LLM_API_BASE})")
    except Exception as e:
        print(f"  ⚠ LLM API 连接失败: {e}")
        print("  将继续启动，但 AI 功能可能无法正常使用")
    return True


def check_discord() -> bool:
    """验证 Discord 配置。"""
    from config import config
    if not config.DISCORD_BOT_TOKEN:
        print("  ❌ Discord Bot Token 未配置（请检查 .env）")
        return False
    if not config.DISCORD_CHANNEL_ID:
        print("  ❌ Discord 频道 ID 未配置（请检查 .env）")
        return False
    print(f"  ✓ Discord 配置就绪 (频道: {config.DISCORD_CHANNEL_ID})")
    return True


# ─────────────────────────────────────────────────────────────────
# 章节压缩辅助
# ─────────────────────────────────────────────────────────────────

class _Tee:
    """将 stdout 同时写入真实终端和内部缓冲区，并计行数。"""
    def __init__(self, real):
        self._real = real
        self._buf  = io.StringIO()
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
    运行 fn(*args, **kwargs)，同时捕获它打印的行数。
    - 若成功（返回值非 False 且输出中无 ❌）：
        用 ANSI 上移光标 + 清除到底 把整块输出折叠为一行摘要。
    - 若失败：保留完整输出不动。
    返回 fn 的原始返回值。
    """
    _B = "\033[94m"   # Bright Blue
    _G = "\033[90m"   # Dark Gray
    _C = "\033[96m"   # Bright Cyan
    _R = "\033[0m"

    tee = _Tee(sys.stdout)
    sys.stdout = tee
    try:
        result = fn(*args, **kwargs)
    finally:
        sys.stdout = tee._real

    output   = tee.getvalue()
    n_lines  = tee.lines
    failed   = (result is False) or ("❌" in output)

    if not failed and n_lines > 1:
        # 上移 n_lines 行，清除到屏幕底
        sys.stdout.write(f"\033[{n_lines}A\033[J")
        sys.stdout.write(f"  {_B}✓{_R}  {_G}{title}{_R}\n")
        sys.stdout.flush()

    return result


# ─────────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────────

def main():
    # 确保工作目录为项目根目录（通过 scripts 入口调用时 cwd 可能不同）
    os.chdir(_DIR)

    print_banner()

    # ANSI 颜色（banner 已激活 VT100，此处可直接使用）
    _R = "\033[0m"
    _B = "\033[94m"
    _W = "\033[97m"
    _C = "\033[96m"
    _G = "\033[90m"

    def _launch(title: str) -> None:
        bar = "─" * 62
        print(f"\n  {_B}{bar}{_R}")
        print(f"  {_C}  ✦  {_W}{title}{_C}  ✦{_R}")
        print(f"  {_B}{bar}{_R}\n")

    print(f"  {_B}┌─{_W} 启动检查 {_R}\n")

    # 0. 引导配置（.env 写入）
    from config import setup
    _run_section("配置初始化", setup)

    # 1. 核心依赖
    if not _run_section("核心 Python 依赖", install_core_deps):
        input("\n按回车退出...")
        sys.exit(1)

    # 2. Playwright 浏览器
    _run_section("Playwright Chromium", install_playwright_browser)

    # 3. 外部工具
    _run_section("外部工具", check_external_tools)

    # 4. Skill 依赖
    _run_section("Skill 技能依赖", check_skill_deps)

    # 5. 目录
    _run_section("初始化目录", check_dirs)

    # 配置验证
    if not _run_section("LLM API 连接", check_api):
        input("\n按回车退出...")
        sys.exit(1)
    if not _run_section("Discord 配置", check_discord):
        input("\n按回车退出...")
        sys.exit(1)

    # 启动
    _launch("Starbot 正在连接星际通信频道...")
    from comms.discord_client import start_discord
    start_discord()


if __name__ == "__main__":
    main()
