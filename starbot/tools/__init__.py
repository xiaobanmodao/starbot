import inspect
import json
from typing import Callable, Any

_TOOLS: dict[str, dict] = {}


def tool(name: str, description: str, params: dict, dangerous: bool = False):
    """Decorator to register a tool with OpenAI function calling schema."""
    def decorator(fn: Callable):
        _TOOLS[name] = {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": params["properties"],
                           "required": params.get("required", [])},
            "dangerous": dangerous,
            "fn": fn,
        }
        return fn
    return decorator


def get_all_tools() -> dict[str, dict]:
    return _TOOLS


def get_openai_tools() -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["parameters"],
        }}
        for t in _TOOLS.values()
    ]


async def call_tool(name: str, arguments: str | dict) -> str:
    if name not in _TOOLS:
        return json.dumps({"error": f"Unknown tool: {name}"})
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    fn = _TOOLS[name]["fn"]
    if inspect.iscoroutinefunction(fn):
        result = await fn(**args)
    else:
        result = fn(**args)
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)


def is_dangerous(name: str) -> bool:
    return _TOOLS.get(name, {}).get("dangerous", False)
