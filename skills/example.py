"""Example Starbot skill — demonstrates the skill format.

Install with:
    /skill install <path_to_this_file>

Skill format requirements:
- META dict with name, version, description, author
- TOOLS list using OpenAI function-calling schema
- execute(name, args) -> dict handler
"""

META = {
    "name": "example",
    "version": "1.0.0",
    "description": "示例 skill：echo 和 timestamp 两个演示工具",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "原样返回输入文字（演示工具）",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "要回显的内容"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_timestamp",
            "description": "返回当前 Unix 时间戳（演示工具）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def execute(name: str, args: dict) -> dict:
    import time

    if name == "echo":
        return {"ok": True, "result": args.get("message", "")}
    if name == "get_timestamp":
        return {"ok": True, "result": str(int(time.time()))}
    return {"ok": False, "result": f"Unknown tool: {name}"}
