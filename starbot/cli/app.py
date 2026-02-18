import asyncio
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from ..agent import Agent, Event


console = Console()


async def run_cli(cfg: dict):
    agent = Agent(cfg)
    session = PromptSession(history=InMemoryHistory())
    console.print(Panel("StarBot - 本地 AI 智能体", style="bold cyan"))
    console.print("输入问题开始对话，输入 /clear 清空历史，/exit 退出\n")

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, lambda: session.prompt("You> ")
            )
        except (EOFError, KeyboardInterrupt):
            break

        text = user_input.strip()
        if not text:
            continue
        if text == "/exit":
            break
        if text == "/clear":
            agent.reset()
            console.print("[dim]对话已清空[/dim]\n")
            continue

        console.print()
        md_buffer = []

        async for event in agent.run(text):
            if event.type == Event.TEXT:
                md_buffer.append(event.data["content"])
            elif event.type == Event.TOOL_CALL:
                _flush_md(md_buffer)
                name = event.data["name"]
                args = event.data["arguments"]
                console.print(f"\n[bold yellow]🔧 调用工具: {name}[/bold yellow]")
                console.print(Panel(args, title="参数", border_style="yellow"))
            elif event.type == Event.CONFIRM:
                _flush_md(md_buffer)
                answer = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: session.prompt("允许执行？(y/n) > ")
                )
                agent.confirm(answer.strip().lower() in ("y", "yes", ""))
            elif event.type == Event.TOOL_RESULT:
                result = event.data["result"]
                display = result[:2000] + "..." if len(result) > 2000 else result
                console.print(Panel(display, title="结果", border_style="green"))
            elif event.type == Event.ERROR:
                _flush_md(md_buffer)
                console.print(f"[bold red]{event.data['message']}[/bold red]")

        _flush_md(md_buffer)
        console.print()

    console.print("[dim]再见！[/dim]")


def _flush_md(buffer: list):
    if buffer:
        text = "".join(buffer)
        console.print(Markdown(text))
        buffer.clear()
