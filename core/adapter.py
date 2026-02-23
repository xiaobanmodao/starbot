import base64
from openai import OpenAI


class UniversalLLM:
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.model = model_name
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=120)

    def chat(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

