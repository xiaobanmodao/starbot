from openai import AsyncOpenAI
from typing import AsyncGenerator


class Client:
    def __init__(self, cfg: dict):
        self.client = AsyncOpenAI(
            api_key=cfg["api_key"] or "sk-placeholder",
            base_url=cfg["base_url"],
        )
        self.model = cfg["model"]
        self.temperature = cfg["temperature"]
        self.max_tokens = cfg["max_tokens"]

    async def chat_stream(self, messages: list[dict], tools: list[dict] | None = None) -> AsyncGenerator:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
        stream = await self.client.chat.completions.create(**kwargs)
        async for chunk in stream:
            yield chunk
