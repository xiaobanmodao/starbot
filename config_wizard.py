import os
from typing import Iterable


def _cfg():
    # Local import avoids circular import issues when config.py calls into this module.
    import config as _config_module
    return _config_module


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


def _is_set(key: str) -> bool:
    return bool(os.environ.get(key, "").strip())


def _mask_secret(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _write_env_and_os(key: str, value: str):
    cfg = _cfg()
    cfg._write_env(key, value)
    os.environ[key] = value


def _pick_model(api_base: str, api_key: str) -> str:
    """Fetch models from API and let user pick interactively."""
    from openai import OpenAI

    try:
        client = OpenAI(api_key=api_key, base_url=api_base)
        models = [m.id for m in client.with_options(timeout=10).models.list().data]
    except Exception as e:
        print(f"  Failed to fetch model list: {e}")
        return input("  Enter model name manually: ").strip()

    if not models:
        return input("  API returned no models. Enter model name manually: ").strip()

    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
    except Exception:
        print("  prompt_toolkit unavailable, please enter model name manually.")
        return input("  Enter model name manually: ").strip()

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


def _infer_provider_from_base(api_base: str) -> str:
    base = (api_base or "").strip().rstrip("/")
    for key, preset in _LLM_PROVIDER_PRESETS.items():
        if preset["base"] and preset["base"].rstrip("/") == base:
            return key
    return "custom"


def _step_choice_if_configured_ui(
    title: str,
    step_name: str,
    field_keys: Iterable[str],
    summary_lines: list[str] | None = None,
) -> bool:
    keys = list(field_keys)
    if not keys or not all(_is_set(k) for k in keys):
        return True
    text = f"{step_name} is already configured.\n\n"
    if summary_lines:
        text += "\n".join(summary_lines) + "\n\n"
    text += "Choose what to do:"
    choice = _ui_choice(
        title=title,
        text=text,
        values=[
            ("skip", "Skip (keep current values)"),
            ("modify", "Modify this step"),
        ],
        default="skip",
    )
    return choice == "modify"


def _step_choice_if_configured_plain(step_name: str, field_keys: Iterable[str], summary_lines: list[str] | None = None) -> bool:
    keys = list(field_keys)
    if not keys or not all(_is_set(k) for k in keys):
        return True
    print(f"\n[{step_name}] already configured.")
    if summary_lines:
        for line in summary_lines:
            print(f"  {line}")
    while True:
        ans = input("  [S]kip keep current / [M]odify this step? ").strip().lower()
        if ans in ("", "s", "skip"):
            return False
        if ans in ("m", "modify"):
            return True
        print("  Please enter S or M.")


def _wizard_step_llm_ui(force: bool):
    if force and not _step_choice_if_configured_ui(
        "Step 1/3 - LLM",
        "LLM configuration",
        ["LLM_API_BASE", "LLM_API_KEY"],
        summary_lines=[
            f"LLM_API_BASE = {os.environ.get('LLM_API_BASE', '')}",
            f"LLM_API_KEY = {_mask_secret(os.environ.get('LLM_API_KEY', ''))}",
            f"LLM_MODEL = {os.environ.get('LLM_MODEL', '') or '(not set)'}",
        ],
    ):
        return

    current_base = os.environ.get("LLM_API_BASE", "")
    provider = _ui_choice(
        title="Step 1/3 - LLM",
        text=(
            "Choose your LLM API provider.\n"
            "Use Up/Down to select, Enter to confirm.\n"
            "Official providers auto-fill API base URL; custom requires manual input."
        ),
        values=[(k, v["label"]) for k, v in _LLM_PROVIDER_PRESETS.items()],
        default=_infer_provider_from_base(current_base),
    )

    preset = _LLM_PROVIDER_PRESETS[provider]
    api_base = preset["base"]
    if provider == "custom":
        api_base = _ui_input(
            "Step 1/3 - LLM",
            "Enter OpenAI-compatible API base URL (example: https://api.example.com/v1)",
            default=current_base,
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

    _write_env_and_os("LLM_API_BASE", api_base)
    _write_env_and_os("LLM_API_KEY", api_key)

    current_model = os.environ.get("LLM_MODEL", "").strip()
    should_choose_model = not current_model
    if current_model:
        model_action = _ui_choice(
            title="Model Selection",
            text=f"Current model is already set:\n{current_model}\n\nChoose what to do:",
            values=[
                ("keep", "Keep current model"),
                ("reselect", "Re-select / change model"),
            ],
            default="keep",
        )
        should_choose_model = (model_action == "reselect")

    if should_choose_model:
        _ui_message(
            "Model Selection",
            "Starbot will now try to fetch available models from your API.\n"
            "If that fails, you can type the model name manually.",
        )
        model = _pick_model(api_base, api_key)
        if model:
            _write_env_and_os("LLM_MODEL", model)


def _wizard_step_discord_ui(force: bool):
    if force and not _step_choice_if_configured_ui(
        "Step 2/3 - Discord",
        "Discord configuration",
        ["DISCORD_BOT_TOKEN", "DISCORD_OWNER_ID", "DISCORD_CHANNEL_ID"],
        summary_lines=[
            f"DISCORD_BOT_TOKEN = {_mask_secret(os.environ.get('DISCORD_BOT_TOKEN', ''))}",
            f"DISCORD_OWNER_ID = {os.environ.get('DISCORD_OWNER_ID', '')}",
            f"DISCORD_CHANNEL_ID = {os.environ.get('DISCORD_CHANNEL_ID', '')}",
        ],
    ):
        return

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

    _write_env_and_os("DISCORD_BOT_TOKEN", bot_token)
    _write_env_and_os("DISCORD_OWNER_ID", owner_id)
    _write_env_and_os("DISCORD_CHANNEL_ID", channel_id)


def _wizard_step_proxy_ui(force: bool):
    current_proxy = os.environ.get("DISCORD_PROXY", "").strip()
    if force and current_proxy:
        if not _step_choice_if_configured_ui(
            "Step 3/3 - Proxy",
            "Proxy configuration",
            ["DISCORD_PROXY"],
            summary_lines=[f"DISCORD_PROXY = {current_proxy}"],
        ):
            return

    use_proxy = _ui_choice(
        title="Step 3/3 - Proxy",
        text="Do you want to use a proxy? (Use Up/Down to select, Enter to confirm)",
        values=[
            ("no", "No proxy"),
            ("yes", "Use local HTTP proxy (127.0.0.1:PORT)"),
        ],
        default="yes" if current_proxy else "no",
    )

    proxy_value = ""
    if use_proxy == "yes":
        current_port = ""
        if current_proxy.startswith("http://127.0.0.1:"):
            current_port = current_proxy.rsplit(":", 1)[-1]

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

    _write_env_and_os("DISCORD_PROXY", proxy_value)


def _setup_plain(force: bool = False):
    missing = [(k, p) for k, p in _REQUIRED if not os.environ.get(k, "").strip()]
    if not missing and not force:
        return

    print("=== Starbot Setup Wizard (Plain CLI) ===\n")
    if force:
        print("Configured fields can be skipped or modified.\n")

    llm_keys = ["LLM_API_BASE", "LLM_API_KEY"]
    if (not force) or _step_choice_if_configured_plain(
        "Step 1/3 - LLM",
        llm_keys,
        [
            f"LLM_API_BASE = {os.environ.get('LLM_API_BASE', '')}",
            f"LLM_API_KEY = {_mask_secret(os.environ.get('LLM_API_KEY', ''))}",
            f"LLM_MODEL = {os.environ.get('LLM_MODEL', '') or '(not set)'}",
        ],
    ):
        print("[Step 1/3] LLM")
        current_base = os.environ.get("LLM_API_BASE", "")
        provider_default = _infer_provider_from_base(current_base)
        print("  Providers:")
        provider_keys = list(_LLM_PROVIDER_PRESETS.keys())
        for idx, key in enumerate(provider_keys, start=1):
            mark = " (default)" if key == provider_default else ""
            print(f"    {idx}. {_LLM_PROVIDER_PRESETS[key]['label']}{mark}")
        while True:
            raw = input("  Choose provider number (Enter=default): ").strip()
            if not raw:
                provider = provider_default
                break
            if raw.isdigit() and 1 <= int(raw) <= len(provider_keys):
                provider = provider_keys[int(raw) - 1]
                break
            print("    Invalid choice, retry.")

        if provider == "custom":
            while True:
                api_base = input(f"  API base URL [{current_base}]: ").strip() or current_base
                if api_base:
                    break
                print("    Value cannot be empty.")
        else:
            api_base = _LLM_PROVIDER_PRESETS[provider]["base"]
            print(f"  Using API base URL: {api_base}")

        while True:
            cur_key_hint = _mask_secret(os.environ.get("LLM_API_KEY", ""))
            api_key = input(f"  API key [{cur_key_hint} / Enter to keep current]: ").strip()
            if api_key:
                break
            api_key = os.environ.get("LLM_API_KEY", "").strip()
            if api_key:
                break
            print("    Value cannot be empty.")

        _write_env_and_os("LLM_API_BASE", api_base)
        _write_env_and_os("LLM_API_KEY", api_key)

        cur_model = os.environ.get("LLM_MODEL", "").strip()
        choose_model = not cur_model
        if cur_model and force:
            while True:
                ans = input(f"  Model already set ({cur_model}). [K]eep / [C]hange? ").strip().lower()
                if ans in ("", "k", "keep"):
                    choose_model = False
                    break
                if ans in ("c", "change"):
                    choose_model = True
                    break
                print("    Please enter K or C.")
        if choose_model:
            print("  Fetching model list from API...")
            model = _pick_model(api_base, api_key)
            if model:
                _write_env_and_os("LLM_MODEL", model)

    discord_keys = ["DISCORD_BOT_TOKEN", "DISCORD_OWNER_ID", "DISCORD_CHANNEL_ID"]
    if (not force) or _step_choice_if_configured_plain(
        "Step 2/3 - Discord",
        discord_keys,
        [
            f"DISCORD_BOT_TOKEN = {_mask_secret(os.environ.get('DISCORD_BOT_TOKEN', ''))}",
            f"DISCORD_OWNER_ID = {os.environ.get('DISCORD_OWNER_ID', '')}",
            f"DISCORD_CHANNEL_ID = {os.environ.get('DISCORD_CHANNEL_ID', '')}",
        ],
    ):
        print("\n[Step 2/3] Discord")
        print("  1) Create bot at https://discord.com/developers/applications")
        print("  2) Enable Message Content Intent")
        print("  3) Invite bot with bot + applications.commands scopes")
        print("  4) Copy Bot Token / Owner ID / Channel ID")

        while True:
            cur = _mask_secret(os.environ.get("DISCORD_BOT_TOKEN", ""))
            bot_token = input(f"  Discord Bot Token [{cur} / Enter to keep current]: ").strip()
            if bot_token:
                break
            bot_token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
            if bot_token:
                break
            print("    Value cannot be empty.")

        while True:
            owner_id = input(f"  Owner User ID [{os.environ.get('DISCORD_OWNER_ID', '')}]: ").strip() or os.environ.get("DISCORD_OWNER_ID", "").strip()
            if owner_id.isdigit():
                break
            print("    Must be numeric.")

        while True:
            channel_id = input(f"  Default Notify Channel ID [{os.environ.get('DISCORD_CHANNEL_ID', '')}]: ").strip() or os.environ.get("DISCORD_CHANNEL_ID", "").strip()
            if channel_id.isdigit():
                break
            print("    Must be numeric.")

        _write_env_and_os("DISCORD_BOT_TOKEN", bot_token)
        _write_env_and_os("DISCORD_OWNER_ID", owner_id)
        _write_env_and_os("DISCORD_CHANNEL_ID", channel_id)

    if (not force) or _step_choice_if_configured_plain(
        "Step 3/3 - Proxy",
        ["DISCORD_PROXY"],
        [f"DISCORD_PROXY = {os.environ.get('DISCORD_PROXY', '') or '(none)'}"],
    ):
        print("\n[Step 3/3] Proxy")
        current_proxy = os.environ.get("DISCORD_PROXY", "")
        while True:
            default = "y" if current_proxy else "n"
            ans = input(f"  Use proxy? [y/N] (default={default.upper()}): ").strip().lower()
            if not ans:
                ans = default
            if ans in ("y", "yes", "n", "no"):
                break
            print("    Please enter y or n.")

        proxy_value = ""
        if ans in ("y", "yes"):
            current_port = ""
            if current_proxy.startswith("http://127.0.0.1:"):
                current_port = current_proxy.rsplit(":", 1)[-1]
            while True:
                port = input(f"  Proxy port [{current_port or '7890'}]: ").strip() or (current_port or "7890")
                if port.isdigit() and 1 <= int(port) <= 65535:
                    proxy_value = f"http://127.0.0.1:{port}"
                    break
                print("    Invalid port.")
        _write_env_and_os("DISCORD_PROXY", proxy_value)

    print("\nSaved configuration to .env\n")


def run_setup_wizard(*, force: bool = False):
    missing = [(k, p) for k, p in _REQUIRED if not os.environ.get(k, "").strip()]
    if not missing and not force:
        return None

    try:
        intro = (
            "Starbot setup wizard.\n\n"
            "Steps:\n"
            "1) LLM API (base URL + API key)\n"
            "2) Discord (Bot Token / Owner ID / Default notify channel ID)\n"
            "3) Proxy (optional)\n\n"
            "For selection dialogs: Up/Down to move, Enter to confirm."
        )
        if force:
            intro = (
                "Starbot configuration wizard (reconfigure mode).\n\n"
                "Already configured steps can be skipped or modified.\n\n" + intro
            )
        else:
            intro = "Incomplete configuration detected.\n\n" + intro

        _ui_message("Starbot Setup Wizard", intro)
        _wizard_step_llm_ui(force=force)
        _wizard_step_discord_ui(force=force)
        _wizard_step_proxy_ui(force=force)
        _ui_message("Setup Complete", "Configuration has been saved to .env.\nYou can continue startup now.")
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        raise
    except Exception:
        _cfg().log.exception("Interactive setup failed; falling back to plain prompts")
        _setup_plain(force=force)

    return True


def main():
    run_setup_wizard(force=True)


if __name__ == "__main__":
    main()
