import os
import glob as globmod
from . import tool


@tool(
    name="file_read",
    description="Read file content. Returns the text content of a file.",
    params={
        "properties": {
            "path": {"type": "string", "description": "File path to read"}
        },
        "required": ["path"],
    },
)
def file_read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[error] {e}"


@tool(
    name="file_write",
    description="Write content to a file. Creates parent directories if needed.",
    params={
        "properties": {
            "path": {"type": "string", "description": "File path to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    },
    dangerous=True,
)
def file_write(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"[error] {e}"


@tool(
    name="file_search",
    description="Search for files matching a glob pattern, optionally grep content.",
    params={
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
            "grep": {"type": "string", "description": "Optional text to search inside files"},
        },
        "required": ["pattern"],
    },
)
def file_search(pattern: str, grep: str = "") -> str:
    try:
        files = globmod.glob(pattern, recursive=True)[:100]
        if not grep:
            return "\n".join(files) if files else "No files found"
        results = []
        for f in files:
            try:
                with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if grep in line:
                            results.append(f"{f}:{i}: {line.rstrip()}")
            except (IsADirectoryError, PermissionError):
                continue
        return "\n".join(results[:50]) if results else "No matches found"
    except Exception as e:
        return f"[error] {e}"
