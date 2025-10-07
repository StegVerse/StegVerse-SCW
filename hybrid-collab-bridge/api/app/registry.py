import yaml
from typing import Dict, List
from .providers.base import Provider
from .providers.anthropic_text import AnthropicText
from .providers.mock_text import MockText  # <-- add this

FACTORY = {
    "anthropic_text": AnthropicText,
    "mock_text": MockText,                # <-- add this
}

class ProviderRegistry:
    def __init__(self, cfg_path: str = "providers.yaml"):
        self.cfg_path = cfg_path
        self.providers: Dict[str, Provider] = {}
        self.reload()

    def reload(self):
        with open(self.cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.providers = {}
        for p in cfg.get("providers", []):
            if not p.get("enabled", True):
                continue
            typ = p["type"]; name = p["name"]
            cls = FACTORY.get(typ)
            if not cls: continue
            self.providers[name] = cls(name)

    def get(self, name: str) -> Provider | None:
        return self.providers.get(name)

    def list(self) -> List[str]:
        return list(self.providers.keys())
