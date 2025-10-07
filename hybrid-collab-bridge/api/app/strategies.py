from typing import List, Dict, Any
from .tasks import Task
from .registry import ProviderRegistry

async def consensus(reg: ProviderRegistry, experts: List[str], prompt: str, opts: Dict[str,Any]) -> Dict[str, Any]:
    proposals = []
    for name in experts:
        prov = reg.get(name)
        if not prov or not prov.supports("text-generate"):
            continue
        out = await prov.run(Task("text-generate", prompt, opts))
        proposals.append({"who": name, "out": out})

    if proposals:
        referee = reg.get(experts[0])
        merged_prompt = "Synthesize a concise final answer from these proposals:\n\n"
        for p in proposals:
            merged_prompt += f"- {p['who']}: {p['out'].get('text','')}\n"
        merged = await referee.run(Task("text-generate", merged_prompt, {"temperature": 0.2}))
    else:
        merged = {"text": "No proposals."}

    return {"proposals": proposals, "final": merged}
