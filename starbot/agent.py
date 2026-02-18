import json
from typing import AsyncGenerator
from .client import Client
from .conversation import Conversation
from .tools import get_openai_tools, call_tool, is_dangerous


class Event:
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    CONFIRM = "confirm"

    def __init__(self, type: str, **data):
        self.type = type
        self.data = data


class Agent:
    def __init__(self, cfg: dict):
        self.client = Client(cfg["model"])
        self.conv = Conversation(cfg["agent"]["system_prompt"])
        self.max_iterations = cfg["agent"]["max_iterations"]
        self.confirm_dangerous = cfg["agent"]["confirm_dangerous"]
        self._pending_confirm = None

    def confirm(self, approved: bool):
        self._pending_confirm = approved

    async def run(self, user_input: str) -> AsyncGenerator[Event, None]:
        self.conv.add_user(user_input)
        tools = get_openai_tools()

        for _ in range(self.max_iterations):
            text_parts = []
            tool_calls_map = {}

            async for chunk in self.client.chat_stream(self.conv.get_messages(), tools or None):
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue
                if delta.content:
                    text_parts.append(delta.content)
                    yield Event(Event.TEXT, content=delta.content)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                        if tc.id:
                            tool_calls_map[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_map[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_map[idx]["arguments"] += tc.function.arguments

            full_text = "".join(text_parts) or None
            if not tool_calls_map:
                self.conv.add_assistant(content=full_text)
                return

            # Build tool_calls for conversation
            tc_list = [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls_map.values()
            ]
            self.conv.add_assistant(content=full_text, tool_calls=tc_list)

            # Execute each tool call
            for tc in tool_calls_map.values():
                name, args_str = tc["name"], tc["arguments"]
                yield Event(Event.TOOL_CALL, name=name, arguments=args_str, id=tc["id"])

                # Dangerous tool confirmation
                if self.confirm_dangerous and is_dangerous(name):
                    self._pending_confirm = None
                    yield Event(Event.CONFIRM, name=name, arguments=args_str, id=tc["id"])
                    # Wait for confirmation (set by caller)
                    if self._pending_confirm is False:
                        result = "[user denied execution]"
                        self.conv.add_tool_result(tc["id"], result)
                        yield Event(Event.TOOL_RESULT, name=name, result=result, id=tc["id"])
                        continue

                try:
                    result = await call_tool(name, args_str)
                except Exception as e:
                    result = f"[error] {e}"
                self.conv.add_tool_result(tc["id"], result)
                yield Event(Event.TOOL_RESULT, name=name, result=result, id=tc["id"])

        yield Event(Event.ERROR, message="Max iterations reached")

    def reset(self):
        self.conv.clear()
