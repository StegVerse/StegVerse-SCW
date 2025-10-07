from typing import Literal, Dict, Any

TaskType = Literal["text-generate"]

class Task:
    def __init__(self, task_type: TaskType, prompt: str, options: Dict[str, Any] | None = None):
        self.task_type = task_type
        self.prompt = prompt
        self.options = options or {}
