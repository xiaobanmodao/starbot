import io
import os
import sys
import subprocess
import shutil
import glob

_DIR = os.path.dirname(os.path.abspath(__file__))

# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 鏍稿績 Python 渚濊禆  (import_name, pip_install_spec)
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
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

# Skill 涓撳睘渚濊禆 (skill 鏂囦欢鍚?鈫?[(import_name, pip_spec), ...])
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

# 鐩綍鍒楄〃锛堢浉瀵归」鐩牴锛?
REQUIRED_DIRS = [
    "logs",
    "logs/frames",
    "logs/subs",
    "logs/video_learn",
    "skills",
]


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# Banner
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def print_banner() -> None:
    """鎵撳嵃 Starbot 鏄熺┖椋庢牸 ASCII 鑹烘湳 Banner銆?""
    if sys.platform == "win32":
        os.system("")  # 婵€娲?Windows 鎺у埗鍙?ANSI/VT100 鏀寔

    R = "\033[0m"   # Reset
    B = "\033[94m"  # Bright Blue
    W = "\033[97m"  # Bright White
    C = "\033[96m"  # Bright Cyan
    G = "\033[90m"  # Dark Gray

    stars_a = (
        f"  {C}鉁G}路 {R}  {B}鉁R}   {G}路{R}  {C}鉁R}   {G}路{R}  "
        f"{B}鉁R}   {G}路{R}   {C}鉁R}  {G}路{R}  {B}鉁R}   {G}路{R}  "
        f"{C}鉁R}  {G}路{R}  {B}鉁G}路{R}"
    )
    stars_b = (
        f"  {G}路{R}  {B}鉁R}   {G}路{R}    {C}鉁R}   {G}路{R}  "
        f"{B}鉁R}    {G}路{R}   {C}鉁R}  {G}路{R}    {B}鉁R}   "
        f"{G}路{R}  {C}鉁G}路{R}  {B}鉁R}"
    )

    # ANSI Shadow 瀛椾綋椋庢牸锛岃摑鐧戒氦鏇挎笎鍙?    logo = [
        f"  {B}鈻堚枅鈻堚枅鈻堚枅鈻堚晽{W}鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈺梴B} 鈻堚枅鈻堚枅鈻堚晽 {W}鈻堚枅鈻堚枅鈻堚枅鈺?{B}鈻堚枅鈻堚枅鈻堚枅鈺? {W}鈻堚枅鈻堚枅鈻堚枅鈺?{B}鈻堚枅鈻堚枅鈻堚枅鈻堚枅鈺梴R}",
        f"  {B}鈻堚枅鈺斺晲鈺愨晲鈺愨暆{W}鈺氣晲鈺愨枅鈻堚晹鈺愨晲鈺漿B}鈻堚枅鈺斺晲鈺愨枅鈻堚晽{W}鈻堚枅鈺斺晲鈺愨枅鈻堚晽{B}鈻堚枅鈺斺晲鈺愨枅鈻堚晽{W}鈻堚枅鈺斺晲鈺愨晲鈻堚枅鈺梴B}鈺氣晲鈺愨枅鈻堚晹鈺愨晲鈺漿R}",
        f"  {W}鈻堚枅鈻堚枅鈻堚枅鈻堚晽{B}   鈻堚枅鈺?  {W}鈻堚枅鈻堚枅鈻堚枅鈻堚晳{B}鈻堚枅鈻堚枅鈻堚枅鈺斺暆{W}鈻堚枅鈻堚枅鈻堚枅鈺斺暆{B}鈻堚枅鈺?  鈻堚枅鈺憑W}   鈻堚枅鈺?  {R}",
        f"  {B}鈺氣晲鈺愨晲鈺愨枅鈻堚晳{W}   鈻堚枅鈺?  {B}鈻堚枅鈺斺晲鈺愨枅鈻堚晳{W}鈻堚枅鈺斺晲鈺愨枅鈻堚晽{B}鈻堚枅鈺斺晲鈺愨枅鈻堚晽{W}鈻堚枅鈺?  鈻堚枅鈺憑B}   鈻堚枅鈺?  {R}",
        f"  {W}鈻堚枅鈻堚枅鈻堚枅鈻堚晳{B}   鈻堚枅鈺?  {W}鈻堚枅鈺? 鈻堚枅鈺憑B}鈻堚枅鈺? 鈻堚枅鈺憑W}鈻堚枅鈻堚枅鈻堚枅鈺斺暆{B}鈺氣枅鈻堚枅鈻堚枅鈻堚晹鈺漿W}   鈻堚枅鈺?  {R}",
        f"  {B}鈺氣晲鈺愨晲鈺愨晲鈺愨暆{W}   鈺氣晲鈺?  {B}鈺氣晲鈺? 鈺氣晲鈺漿W}鈺氣晲鈺? 鈺氣晲鈺漿B}鈺氣晲鈺愨晲鈺愨晲鈺?{W} 鈺氣晲鈺愨晲鈺愨晲鈺?{B}   鈺氣晲鈺?  {R}",
    ]

    div = f"  {B}{'鈹€' * 64}{R}"

    print()
    print(stars_a)
    print()
    for line in logo:
        print(line)
    print()
    print(f"  {C}鉁? AI 椹卞姩鐨?Windows 妗岄潰鑷姩鍖栧姪鎵? 路  v0.1.0  鉁R}")
    print(f"  {G}Discord 路 ReAct 鎺ㄧ悊寮曟搸 路 50+ 宸ュ叿 路 OpenAI / Claude / DeepSeek{R}")
    print()
    print(div)
    print()
    print(stars_b)
    print()


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 宸ュ叿鍑芥暟
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _installer() -> list:
    """杩斿洖瀹夎鍛戒护鍓嶇紑锛歶v pip install 鎴?pip install銆?""
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
    """瀹夎鑻ュ共 pip 鍖咃紝杩斿洖鏄惁鍏ㄩ儴鎴愬姛銆?""
    if not packages:
        return True
    cmd = _installer() + packages
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  鉂?瀹夎澶辫触:\n{r.stderr[:600]}")
        return False
    return True


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 妫€鏌ユ楠?# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def install_core_deps() -> bool:
    """[1/5] 妫€鏌ュ苟瀹夎鎵€鏈夋牳蹇?Python 渚濊禆銆?""
    print("[1/5] 鏍稿績 Python 渚濊禆")
    missing = []
    for import_name, pkg in CORE_DEPS:
        if _can_import(import_name):
            print(f"  鉁?{import_name}")
        else:
            print(f"  鉁?{import_name}  鈫? 寰呭畨瑁?{pkg}")
            missing.append(pkg)

    if not missing:
        print("  鈫?鍏ㄩ儴灏辩华\n")
        return True

    print(f"\n  姝ｅ湪瀹夎 {len(missing)} 涓己澶卞寘...")
    if not _pip_install(missing):
        return False
    print("  鈫?瀹夎瀹屾垚\n")
    return True


def install_playwright_browser() -> None:
    """[2/5] 纭繚 Playwright Chromium 娴忚鍣ㄥ凡涓嬭浇銆?""
    print("[2/5] Playwright Chromium 娴忚鍣?)

    if not _can_import("playwright"):
        print("  鈿?playwright 鏈畨瑁咃紝璺宠繃锛坆rowser_agent 鎶€鑳藉皢涓嶅彲鐢級\n")
        return

    # 灏濊瘯閫氳繃 playwright CLI 瀹夎 chromium锛堝凡瑁呭垯绉掑畬鎴愶級
    install_cmds = [
        ["playwright", "install", "chromium"],
        [sys.executable, "-m", "playwright", "install", "chromium"],
    ]
    installed = False
    for cmd in install_cmds:
        if cmd[0] == sys.executable or shutil.which(cmd[0]):
            print("  姝ｅ湪纭 Chromium 宸插畨瑁咃紙棣栨涓嬭浇绾?130 MB锛?..")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                print("  鉁?Chromium 灏辩华\n")
                installed = True
                break

    if not installed:
        print("  鈿?Chromium 瀹夎澶辫触锛岃鎵嬪姩杩愯: playwright install chromium\n")


def check_external_tools() -> None:
    """[3/5] 妫€鏌ュ閮ㄥ懡浠よ宸ュ叿锛坹t-dlp銆乀esseract锛夈€?""
    print("[3/5] 澶栭儴宸ュ叿")

    # yt-dlp锛氫紭鍏?PATH锛屽叾娆℃ā鍧楄皟鐢?    if shutil.which("yt-dlp"):
        r = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        ver = r.stdout.strip()
        print(f"  鉁?yt-dlp {ver}")
    else:
        r = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            print(f"  鉁?yt-dlp (妯″潡) {r.stdout.strip()}")
        else:
            print("  鈿?yt-dlp 涓嶅彲鐢紝瑙嗛/闊抽涓嬭浇鍔熻兘鍙楅檺")

    # Tesseract OCR锛堝彲閫夛級
    if shutil.which("tesseract"):
        r = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
        ver = (r.stdout or r.stderr).splitlines()[0] if r.stdout or r.stderr else "?"
        print(f"  鉁?Tesseract OCR: {ver}")
    else:
        print("  鈿?Tesseract OCR 鏈畨瑁咃紙鍙€夛紝鐢ㄤ簬鎴浘鏂囧瓧璇嗗埆锛?)
        print("    涓嬭浇鍦板潃: https://github.com/UB-Mannheim/tesseract/wiki")

    print()


def check_skill_deps() -> bool:
    """[4/5] 鎵弿 skills/ 骞跺畨瑁呭悇鎶€鑳芥墍闇€渚濊禆銆?""
    print("[4/5] Skill 鎶€鑳戒緷璧?)

    skills_dir = os.path.join(_DIR, "skills")
    if not os.path.isdir(skills_dir):
        print("  (skills/ 鐩綍涓嶅瓨鍦紝璺宠繃)\n")
        return True

    skill_files = sorted(glob.glob(os.path.join(skills_dir, "*.py")))
    if not skill_files:
        print("  (鏃犳妧鑳芥枃浠讹紝璺宠繃)\n")
        return True

    all_missing: list = []
    for skill_path in skill_files:
        name = os.path.splitext(os.path.basename(skill_path))[0]
        if name.startswith("_") or name == "example":
            continue

        deps = SKILL_DEPS.get(name, [])
        bad = [pkg for imp, pkg in deps if not _can_import(imp)]
        if bad:
            print(f"  鉁?{name}: 缂哄皯 {', '.join(bad)}")
            all_missing.extend(bad)
        else:
            print(f"  鉁?{name}")

    if all_missing:
        # 鍘婚噸淇濆簭
        seen: set = set()
        unique: list = []
        for p in all_missing:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        print(f"\n  姝ｅ湪瀹夎 skill 渚濊禆: {', '.join(unique)}")
        if not _pip_install(unique):
            print("  鈿?閮ㄥ垎 skill 渚濊禆瀹夎澶辫触锛岀浉鍏虫妧鑳藉彲鑳戒笉鍙敤")
        else:
            print("  鈫?Skill 渚濊禆瀹夎瀹屾垚")
    else:
        print("  鈫?鍏ㄩ儴灏辩华")

    print()
    return True


def check_dirs() -> None:
    """[5/5] 纭繚蹇呰鐩綍瀛樺湪銆?""
    print("[5/5] 鍒濆鍖栫洰褰?)
    for d in REQUIRED_DIRS:
        path = os.path.join(_DIR, d)
        os.makedirs(path, exist_ok=True)
        print(f"  鉁?{d}/")
    print()


def check_api() -> bool:
    """楠岃瘉 LLM API 杩為€氭€с€?""
    from config import config
    if not config.LLM_API_BASE or not config.LLM_API_KEY:
        print("  鉂?LLM API 鏈厤缃紙璇锋鏌?.env锛?)
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_API_BASE, timeout=10)
        client.models.list()
        print(f"  鉁?LLM API 杩炴帴姝ｅ父 ({config.LLM_API_BASE})")
    except Exception as e:
        print(f"  鈿?LLM API 杩炴帴澶辫触: {e}")
        print("  灏嗙户缁惎鍔紝浣?AI 鍔熻兘鍙兘鏃犳硶姝ｅ父浣跨敤")
    return True


def check_discord() -> bool:
    """楠岃瘉 Discord 閰嶇疆銆?""
    from config import config
    if not config.DISCORD_BOT_TOKEN:
        print("  鉂?Discord Bot Token 鏈厤缃紙璇锋鏌?.env锛?)
        return False
    if not config.DISCORD_CHANNEL_ID:
        print("  鉂?Discord 棰戦亾 ID 鏈厤缃紙璇锋鏌?.env锛?)
        return False
    print(f"  鉁?Discord 閰嶇疆灏辩华 (棰戦亾: {config.DISCORD_CHANNEL_ID})")
    return True


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 绔犺妭鍘嬬缉杈呭姪
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

class _Tee:
    """灏?stdout 鍚屾椂鍐欏叆鐪熷疄缁堢鍜屽唴閮ㄧ紦鍐插尯锛屽苟璁¤鏁般€?""
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
    杩愯 fn(*args, **kwargs)锛屽悓鏃舵崟鑾峰畠鎵撳嵃鐨勮鏁般€?    - 鑻ユ垚鍔燂紙杩斿洖鍊奸潪 False 涓旇緭鍑轰腑鏃?鉂岋級锛?        鐢?ANSI 涓婄Щ鍏夋爣 + 娓呴櫎鍒板簳 鎶婃暣鍧楄緭鍑烘姌鍙犱负涓€琛屾憳瑕併€?    - 鑻ュけ璐ワ細淇濈暀瀹屾暣杈撳嚭涓嶅姩銆?    杩斿洖 fn 鐨勫師濮嬭繑鍥炲€笺€?    """
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
    has_warning = ("⚠" in output) or ("warning" in output.lower())
    failed   = (result is False) or ("❌" in output)

    # Keep warnings/failures visible instead of collapsing them into one line.
    if not failed and not has_warning and n_lines > 1:
        # 涓婄Щ n_lines 琛岋紝娓呴櫎鍒板睆骞曞簳
        sys.stdout.write(f"\033[{n_lines}A\033[J")
        sys.stdout.write(f"  {_B}鉁搟_R}  {_G}{title}{_R}\n")
        sys.stdout.flush()

    return result


def _parse_start_cli(argv: list[str]) -> dict:
    """Minimal CLI flags for startup/setup workflows."""
    opts = {
        "force_setup": False,
        "setup_only": False,
    }
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


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 鍏ュ彛
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def main():
    # 纭繚宸ヤ綔鐩綍涓洪」鐩牴鐩綍锛堥€氳繃 scripts 鍏ュ彛璋冪敤鏃?cwd 鍙兘涓嶅悓锛?    os.chdir(_DIR)
    os.chdir(_DIR)
    cli = _parse_start_cli(sys.argv[1:])

    print_banner()

    # ANSI 棰滆壊锛坆anner 宸叉縺娲?VT100锛屾澶勫彲鐩存帴浣跨敤锛?    _R = "\033[0m"
    _B = "\033[94m"
    _W = "\033[97m"
    _C = "\033[96m"
    _G = "\033[90m"

    def _launch(title: str) -> None:
        bar = "鈹€" * 62
        print(f"\n  {_B}{bar}{_R}")
        print(f"  {_C}  鉁? {_W}{title}{_C}  鉁_R}")
        print(f"  {_B}{bar}{_R}\n")

    print(f"  {_B}鈹屸攢{_W} 鍚姩妫€鏌?{_R}\n")

    # 0. 寮曞閰嶇疆锛?env 鍐欏叆锛?    from config import setup
    from config import setup
    if cli["setup_only"]:
        print("  Running configuration wizard only (no startup checks).\n")
        setup(force=True)
        return
    if cli["force_setup"]:
        _run_section("閰嶇疆鍒濆鍖? (reconfigure)", setup, True)
    else:
        _run_section("閰嶇疆鍒濆鍖?, setup)

    # 1. 鏍稿績渚濊禆
    if not _run_section("鏍稿績 Python 渚濊禆", install_core_deps):
        input("\n鎸夊洖杞﹂€€鍑?..")
        sys.exit(1)

    # 2. Playwright 娴忚鍣?    _run_section("Playwright Chromium", install_playwright_browser)

    # 3. 澶栭儴宸ュ叿
    _run_section("澶栭儴宸ュ叿", check_external_tools)

    # 4. Skill 渚濊禆
    _run_section("Skill 鎶€鑳戒緷璧?, check_skill_deps)

    # 5. 鐩綍
    _run_section("鍒濆鍖栫洰褰?, check_dirs)

    # 閰嶇疆楠岃瘉
    if not _run_section("LLM API 杩炴帴", check_api):
        input("\n鎸夊洖杞﹂€€鍑?..")
        sys.exit(1)
    if not _run_section("Discord 閰嶇疆", check_discord):
        input("\n鎸夊洖杞﹂€€鍑?..")
        sys.exit(1)

    # 鍚姩
    _launch("Starbot 姝ｅ湪杩炴帴鏄熼檯閫氫俊棰戦亾...")
    from comms.discord_client import start_discord
    start_discord()


if __name__ == "__main__":
    main()


