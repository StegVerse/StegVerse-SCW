from typing import List, Literal, Optional
from pydantic import BaseModel, Field

StrategyName = Literal["consensus","committee"]

class RunRequest(BaseModel):
    slug: str = Field(..., description="folder slug under sessions/YYYY-MM-DD/")
    question: str
    context: Optional[str] = None
    experts: List[str] = Field(default_factory=lambda: ["claude"])
    strategy: StrategyName = "consensus"
    human_gate: bool = True
    temperature: float = 0.4

class ContinueRequest(BaseModel):
    session_path: str

class Turn(BaseModel):
    who: str
    output: str

class RunResponse(BaseModel):
    status: Literal["OK","PAUSED_FOR_REVIEW"]
    session_path: str
    strategy: StrategyName
    turns: List[Turn] = []
    final: Optional[str] = None
