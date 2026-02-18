import os
import yaml
from pathlib import Path

_DEFAULT = {
    "model": {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "agent": {
        "system_prompt": "你是 StarBot，一个强大的本地 AI 助手。你可以执行代码、操作文件、搜索网页、查询数据库等。请用中文回复。",
        "max_iterations": 20,
        "confirm_dangerous": True,
    },
    "web": {"host": "127.0.0.1", "port": 8000},
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _config_path(path: str | None = None) -> Path:
    return Path(path) if path else Path(__file__).parent.parent / "config.yaml"


def setup_wizard(cfg: dict, path: str | None = None):
    """首次运行时引导用户配置 API。"""
    if cfg["model"]["api_key"]:
        return cfg
    print("=" * 50)
    print("  StarBot 首次运行配置")
    print("=" * 50)
    api_key = input("\nAPI Key: ").strip()
    if not api_key:
        print("未输入 API Key，退出。")
        raise SystemExit(1)
    base_url = input(f"Base URL [{cfg['model']['base_url']}]: ").strip()
    model = input(f"模型名称 [{cfg['model']['model']}]: ").strip()

    cfg["model"]["api_key"] = api_key
    if base_url:
        cfg["model"]["base_url"] = base_url
    if model:
        cfg["model"]["model"] = model

    # 写入 config.yaml
    p = _config_path(path)
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
    print(f"\n配置已保存到 {p}\n")
    return cfg


def load_config(path: str | None = None) -> dict:
    cfg = _DEFAULT.copy()
    # load yaml
    p = Path(path) if path else Path(__file__).parent.parent / "config.yaml"
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            file_cfg = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, file_cfg)
    # env overrides
    if v := os.environ.get("STARBOT_API_KEY"):
        cfg["model"]["api_key"] = v
    if v := os.environ.get("STARBOT_BASE_URL"):
        cfg["model"]["base_url"] = v
    if v := os.environ.get("STARBOT_MODEL"):
        cfg["model"]["model"] = v
    return cfg
