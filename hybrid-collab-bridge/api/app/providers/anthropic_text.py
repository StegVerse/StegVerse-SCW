import os, httpx
from typing import Dict, Any
from ..tasks import Task
from .base import Provider

ANTHROPIC_BASE = os.getenv("ANTHROPIC_BASE","https://api.anthropic.com")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL","claude-3-5-sonnet-latest")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT","60"))

class AnthropicText(Provider):
    def __init__(self, name: str):
        super().__init__(name, "anthropic_text", ["text-generate"])
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY missing")
        self.headers = {"x-api-key": key, "anthropic-version":"2023-06-01", "content-type":"application/json"}

    async def run(self, task: Task) -> Dict[str, Any]:
        if task.task_type != "text-generate":
            return {"error":"unsupported task"}
        payload = {
            "model": ANTHROPIC_MODEL,
            "messages": [{"role":"user","content":task.prompt}],
            "max_tokens": 1200,
            "temperature": task.options.get("temperature", 0.4),
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(f"{ANTHROPIC_BASE}/v1/messages", headers=self.headers, json=payload)
            r.raise_for_status()
        data = r.json()
        pieces = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                pieces.append(block.get("text",""))
        return {"text": "\n".join(pieces).strip()}
