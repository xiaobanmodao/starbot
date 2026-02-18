import sys
import io
import traceback
from . import tool

@tool(
    name="python_exec",
    description="Execute Python code and return stdout/stderr output.",
    params={
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"}
        },
        "required": ["code"],
    },
    dangerous=True,
)
def python_exec(code: str) -> str:
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    try:
        exec(code, {"__builtins__": __builtins__})
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        result = out
        if err:
            result += f"\n[stderr]\n{err}"
        return result or "(no output)"
    except Exception:
        return sys.stdout.getvalue() + "\n" + traceback.format_exc()
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
