from abc import ABC, abstractmethod
from typing import List, Dict, Any
from ..tasks import Task

class Provider(ABC):
    name: str
    type: str
    capabilities: List[str]

    def __init__(self, name: str, ptype: str, capabilities: List[str]):
        self.name = name
        self.type = ptype
        self.capabilities = capabilities

    def supports(self, task_type: str) -> bool:
        return task_type in self.capabilities

    @abstractmethod
    async def run(self, task: Task) -> Dict[str, Any]:
        raise NotImplementedError
