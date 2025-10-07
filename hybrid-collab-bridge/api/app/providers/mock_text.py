from ..tasks import Task
from .base import Provider

class MockText(Provider):
    def __init__(self, name: str):
        super().__init__(name, "mock_text", ["text-generate"])

    async def run(self, task: Task):
        if task.task_type != "text-generate":
            return {"error": "unsupported task"}
        # Short, deterministic echo so tests are stable
        snippet = (task.prompt or "")[:120]
        if len(task.prompt or "") > 120:
            snippet += "..."
        return {"text": f"MOCK({self.name}): {snippet}"}
