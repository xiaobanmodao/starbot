import os
import json
import logging
import logging.handlers
from dotenv import load_dotenv

_DIR = os.path.dirname(__file__)
_ENV_FILE = os.path.join(_DIR, ".env")
_STATE_FILE = os.path.join(_DIR, "starbot_state.json")

load_dotenv(_ENV_FILE)


def _setup_logging():
    log_dir = os.path.join(_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "starbot.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)
    ch.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(ch)


_setup_logging()

_REQUIRED = [
    ("LLM_API_BASE", "LLM API 地址 (如 https://api.openai.com/v1)"),
    ("LLM_API_KEY", "LLM API 密钥"),
    ("DISCORD_BOT_TOKEN", "Discord Bot Token"),
    ("DISCORD_OWNER_ID", "Discord 用户 ID (你的用户名或数字ID)"),
    ("DISCORD_CHANNEL_ID", "Discord 频道 ID (数字)"),
]

_OPTIONAL = [
    ("DISCORD_PROXY", "Discord 代理地址 (回车跳过，如 http://127.0.0.1:7897)"),
]


def _load_state() -> dict:
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(data: dict):
    state = _load_state()
    state.update(data)
    with open(_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def _write_env(key: str, value: str):
    lines = []
    found = False
    if os.path.exists(_ENV_FILE):
        with open(_ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    for i, line in enumerate(lines):
        if line.split("#")[0].strip().startswith(key + "="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}\n")
    with open(_ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _pick_model(api_base: str, api_key: str) -> str:
    """Fetch models from API and let user pick interactively."""
    from prompt_toolkit.shortcuts import radiolist_dialog
    from openai import OpenAI
    try:
        client = OpenAI(api_key=api_key, base_url=api_base)
        models = [m.id for m in client.with_options(timeout=10).models.list().data]
    except Exception as e:
        print(f"  获取模型列表失败: {e}")
        return input("  手动输入模型名称: ").strip()
    if not models:
        return input("  API 未返回模型，手动输入模型名称: ").strip()
    result = radiolist_dialog(
        title="选择 LLM 模型",
        text="上下键选择，Enter 确认：",
        values=[(m, m) for m in models],
        default=models[0],
    ).run()
    return result or models[0]


def setup():
    missing = [(k, p) for k, p in _REQUIRED if not os.environ.get(k, "").strip()]
    if not missing:
        return
    print("=== Starbot 首次配置 ===\n")
    for key, prompt_text in missing:
        while True:
            value = input(f"  {prompt_text}: ").strip()
            if value:
                break
            print("    不能为空，请重新输入")
        _write_env(key, value)
        os.environ[key] = value
    # Interactive model selection
    if not os.environ.get("LLM_MODEL", "").strip():
        print("\n  正在获取可用模型列表...")
        model = _pick_model(os.environ["LLM_API_BASE"], os.environ["LLM_API_KEY"])
        if model:
            _write_env("LLM_MODEL", model)
            os.environ["LLM_MODEL"] = model
            print(f"  已选择模型: {model}")
    for key, prompt_text in _OPTIONAL:
        if not os.environ.get(key, "").strip():
            value = input(f"  {prompt_text}: ").strip()
            if value:
                _write_env(key, value)
                os.environ[key] = value
    print("\n配置已保存到 .env 文件\n")


class _Config:
    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self):
        if self._loaded:
            return
        self._loaded = True
        state = _load_state()
        self.LLM_API_BASE = os.environ.get("LLM_API_BASE", "")
        self.LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
        self.LLM_MODEL = state.get("LLM_MODEL") or os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")
        self.LLM2_API_BASE = os.environ.get("LLM2_API_BASE", "")
        self.LLM2_API_KEY = os.environ.get("LLM2_API_KEY", "")
        self.LLM2_MODEL = os.environ.get("LLM2_MODEL", "")
        self.DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
        self.DISCORD_OWNER_ID = os.environ.get("DISCORD_OWNER_ID", "")
        self.DISCORD_CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0") or "0")
        self.DISCORD_PROXY = os.environ.get("DISCORD_PROXY", "")

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        self._load()
        return self.__dict__[name]


config = _Config()
