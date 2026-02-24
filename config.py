import json
import logging
import logging.handlers
import os

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
log = logging.getLogger(__name__)

_REQUIRED = [
    ("LLM_API_BASE", "LLM API base URL (example: https://api.openai.com/v1)"),
    ("LLM_API_KEY", "LLM API key"),
    ("DISCORD_BOT_TOKEN", "Discord Bot Token"),
    ("DISCORD_OWNER_ID", "Discord Owner User ID (numeric)"),
    ("DISCORD_CHANNEL_ID", "Discord default notify channel ID (numeric)"),
]

_OPTIONAL = [
    ("DISCORD_PROXY", "Discord proxy URL (optional, e.g. http://127.0.0.1:7897)"),
]

_LLM_PROVIDER_PRESETS = {
    "openai": {
        "label": "OpenAI (official, auto-fill base URL)",
        "base": "https://api.openai.com/v1",
    },
    "deepseek": {
        "label": "DeepSeek (official, auto-fill base URL)",
        "base": "https://api.deepseek.com/v1",
    },
    "anthropic_compat": {
        "label": "Anthropic-compatible endpoint (auto-fill base URL)",
        "base": "https://api.anthropic.com/v1",
    },
    "custom": {
        "label": "Other OpenAI-compatible endpoint (manual base URL)",
        "base": "",
    },
}


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
        print(f"  Failed to fetch model list: {e}")
        return input("  Enter model name manually: ").strip()

    if not models:
        return input("  API returned no models. Enter model name manually: ").strip()

    result = radiolist_dialog(
        title="Select LLM Model",
        text="Use Up/Down to select, Enter to confirm.",
        values=[(m, m) for m in models],
        default=models[0],
    ).run()
    return result or models[0]


def _ui_message(title: str, text: str):
    from prompt_toolkit.shortcuts import message_dialog

    message_dialog(title=title, text=text).run()


def _ui_choice(title: str, text: str, values: list[tuple[str, str]], default: str | None = None) -> str:
    """Arrow-key selection (up/down) with Enter confirm via radiolist dialog."""
    from prompt_toolkit.shortcuts import radiolist_dialog

    result = radiolist_dialog(
        title=title,
        text=text,
        values=values,
        default=default,
    ).run()
    if result is None:
        raise KeyboardInterrupt("setup cancelled")
    return result


def _ui_input(
    title: str,
    text: str,
    *,
    default: str = "",
    password: bool = False,
    allow_empty: bool = False,
) -> str:
    from prompt_toolkit.shortcuts import input_dialog

    while True:
        result = input_dialog(
            title=title,
            text=text,
            default=default,
            password=password,
        ).run()
        if result is None:
            raise KeyboardInterrupt("setup cancelled")
        value = result.strip()
        if value or allow_empty:
            return value
        _ui_message("Required", "This field is required. Please enter a value.")


def _setup_plain():
    """Fallback setup for environments where prompt_toolkit dialogs are unavailable."""
    missing = [(k, p) for k, p in _REQUIRED if not os.environ.get(k, "").strip()]
    if not missing:
        return

    print("=== Starbot First-Time Setup ===\n")
    for key, prompt_text in missing:
        while True:
            value = input(f"  {prompt_text}: ").strip()
            if value:
                break
            print("    Value cannot be empty, please retry.")
        _write_env(key, value)
        os.environ[key] = value

    if not os.environ.get("LLM_MODEL", "").strip():
        print("\n  Fetching model list from API...")
        model = _pick_model(os.environ["LLM_API_BASE"], os.environ["LLM_API_KEY"])
        if model:
            _write_env("LLM_MODEL", model)
            os.environ["LLM_MODEL"] = model
            print(f"  Selected model: {model}")

    for key, prompt_text in _OPTIONAL:
        if not os.environ.get(key, "").strip():
            value = input(f"  {prompt_text}: ").strip()
            if value:
                _write_env(key, value)
                os.environ[key] = value

    print("\nSaved configuration to .env\n")


def _wizard_step_llm():
    provider = _ui_choice(
        title="Step 1/3 - LLM",
        text=(
            "Choose your LLM API provider.\n"
            "Use Up/Down to select, Enter to confirm.\n"
            "Official providers auto-fill API base URL; custom requires manual input."
        ),
        values=[(k, v["label"]) for k, v in _LLM_PROVIDER_PRESETS.items()],
        default="openai",
    )

    preset = _LLM_PROVIDER_PRESETS[provider]
    api_base = preset["base"]

    if provider == "custom":
        api_base = _ui_input(
            "Step 1/3 - LLM",
            "Enter OpenAI-compatible API base URL (example: https://api.example.com/v1)",
            default=os.environ.get("LLM_API_BASE", ""),
        )
    else:
        _ui_message(
            "Step 1/3 - LLM",
            f"Selected: {preset['label']}\n\nAPI base URL will be set to:\n{api_base}",
        )

    api_key = _ui_input(
        "Step 1/3 - LLM",
        "Enter API key",
        default=os.environ.get("LLM_API_KEY", ""),
        password=True,
    )

    _write_env("LLM_API_BASE", api_base)
    _write_env("LLM_API_KEY", api_key)
    os.environ["LLM_API_BASE"] = api_base
    os.environ["LLM_API_KEY"] = api_key

    if not os.environ.get("LLM_MODEL", "").strip():
        _ui_message(
            "Model Selection",
            "Starbot will now try to fetch available models from your API.\n"
            "If that fails, you can type the model name manually.",
        )
        model = _pick_model(api_base, api_key)
        if model:
            _write_env("LLM_MODEL", model)
            os.environ["LLM_MODEL"] = model


def _wizard_step_discord():
    _ui_message(
        "Step 2/3 - Discord Guide (1/2)",
        (
            "Create a Discord bot first:\n\n"
            "1. Open https://discord.com/developers/applications\n"
            "2. Create a new application\n"
            "3. Go to Bot -> copy Bot Token (you will paste it later)\n"
            "4. Enable Message Content Intent (required)\n"
            "5. Save settings"
        ),
    )

    _ui_message(
        "Step 2/3 - Discord Guide (2/2)",
        (
            "Invite bot and collect IDs:\n\n"
            "1. OAuth2 -> URL Generator -> scopes: bot, applications.commands\n"
            "2. Grant permissions: View Channels, Read Message History, Send Messages,\n"
            "   Attach Files, Embed Links, Create Public Threads\n"
            "3. Invite the bot to your server\n"
            "4. Enable Developer Mode in Discord settings\n"
            "5. Copy your User ID (Owner ID)\n"
            "6. Copy one text Channel ID (Default notify channel)\n\n"
            "Note: Starbot can reply in any text channel (owner only).\n"
            "The default notify channel is used for startup notices,\n"
            "background task completion notices, and monitor alerts."
        ),
    )

    bot_token = _ui_input(
        "Step 2/3 - Discord",
        "Enter Discord Bot Token",
        default=os.environ.get("DISCORD_BOT_TOKEN", ""),
        password=True,
    )

    while True:
        owner_id = _ui_input(
            "Step 2/3 - Discord",
            "Enter Owner User ID (numeric)",
            default=os.environ.get("DISCORD_OWNER_ID", ""),
        )
        if owner_id.isdigit():
            break
        _ui_message("Invalid Owner ID", "Please enter a numeric Discord user ID.")

    while True:
        channel_id = _ui_input(
            "Step 2/3 - Discord",
            "Enter Default Notify Channel ID (numeric)",
            default=os.environ.get("DISCORD_CHANNEL_ID", ""),
        )
        if channel_id.isdigit():
            break
        _ui_message("Invalid Channel ID", "Please enter a numeric Discord channel ID.")

    for key, value in [
        ("DISCORD_BOT_TOKEN", bot_token),
        ("DISCORD_OWNER_ID", owner_id),
        ("DISCORD_CHANNEL_ID", channel_id),
    ]:
        _write_env(key, value)
        os.environ[key] = value


def _wizard_step_proxy():
    use_proxy = _ui_choice(
        title="Step 3/3 - Proxy",
        text="Do you want to use a proxy? (Use Up/Down to select, Enter to confirm)",
        values=[
            ("no", "No proxy"),
            ("yes", "Use local HTTP proxy (127.0.0.1:PORT)"),
        ],
        default="no",
    )

    proxy_value = ""
    if use_proxy == "yes":
        current = os.environ.get("DISCORD_PROXY", "")
        current_port = ""
        if current.startswith("http://127.0.0.1:"):
            current_port = current.rsplit(":", 1)[-1]

        while True:
            port = _ui_input(
                "Step 3/3 - Proxy",
                "Enter proxy port (e.g. 7890)",
                default=current_port,
            )
            if port.isdigit() and 1 <= int(port) <= 65535:
                proxy_value = f"http://127.0.0.1:{port}"
                break
            _ui_message("Invalid Port", "Please enter a number between 1 and 65535.")

    _write_env("DISCORD_PROXY", proxy_value)
    os.environ["DISCORD_PROXY"] = proxy_value


def setup(force: bool = False):
    """Run setup wizard when required, or force reconfiguration when requested."""
    from config_wizard import run_setup_wizard
    return run_setup_wizard(force=force)


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
