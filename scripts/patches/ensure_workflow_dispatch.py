#!/usr/bin/env python3
"""
Ensure every non-reusable workflow has an `on.workflow_dispatch` trigger.
Writes list of changed files to self_healing_out/DISPATCH_INJECTED.txt
"""
import pathlib, sys, yaml

ROOT = pathlib.Path(".")
WF_DIR = ROOT / ".github" / "workflows"
OUT = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)
OUT_LIST = OUT / "DISPATCH_INJECTED.txt"

def load_yaml(p):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def save_yaml(p, data):
    txt = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    p.write_text(txt, encoding="utf-8")

def to_mapping_on(on_val):
    if on_val is None: return {}
    if isinstance(on_val, dict): return on_val
    if isinstance(on_val, list):
        m = {}
        for ev in on_val:
            if isinstance(ev, str):
                m[ev] = {}
        return m
    if isinstance(on_val, str):
        return {on_val: {}}
    return {}

def reusable_only(on_map: dict) -> bool:
    return bool(on_map) and list(on_map.keys()) == ["workflow_call"]

def main():
    if not WF_DIR.exists():
        print("[dispatch] no workflows dir, skipping")
        return 0
    changed = []
    for p in sorted(WF_DIR.glob("*.y*ml")):
        data = load_yaml(p)
        if not isinstance(data, dict):
            continue
        on_map = to_mapping_on(data.get("on"))
        if reusable_only(on_map):
            continue
        if "workflow_dispatch" not in on_map:
            on_map["workflow_dispatch"] = {}
            data["on"] = on_map
            save_yaml(p, data)
            changed.append(str(p))
            print(f"[dispatch] added workflow_dispatch -> {p}")
    OUT_LIST.write_text("\n".join(changed), encoding="utf-8")
    print(f"[dispatch] done; files changed: {len(changed)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
