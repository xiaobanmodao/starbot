import subprocess
import platform
from . import tool

@tool(
    name="shell_exec",
    description="Execute a shell command and return output.",
    params={
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"}
        },
        "required": ["command"],
    },
    dangerous=True,
)
def shell_exec(command: str) -> str:
    try:
        shell = True
        if platform.system() == "Windows":
            args = ["cmd", "/c", command]
            shell = False
        else:
            args = command
        r = subprocess.run(
            args, shell=shell, capture_output=True, text=True, timeout=60
        )
        out = r.stdout
        if r.stderr:
            out += f"\n[stderr]\n{r.stderr}"
        if r.returncode != 0:
            out += f"\n[exit code: {r.returncode}]"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return "[error] Command timed out (60s)"
    except Exception as e:
        return f"[error] {e}"
