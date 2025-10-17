#!/usr/bin/env python3
"""
Self-heal GitHub Actions workflows:
- normalize a few common YAML nits (inline env: {...} => block)
- add `workflow_dispatch` where missing (except reusable-only workflows)
Writes a small summary and an output flag so the workflow can decide to commit.
"""
from __future__ import annotations
import os, re, sys, pathlib, json
from typing import List, Tuple
import yaml  # PyYAML

ROOT = pathlib.Path(".").resolve()
WF_DIR = ROOT / ".github" / "workflows"
OUTDIR = ROOT / ".github" / "autopatch_out"
OUTDIR.mkdir(parents=True, exist_ok=True)

def safe_load(text: str):
    try:
        return yaml.safe_load(text), None
    except Exception as e:
        return None, e

def normalize_inline_env(lines: List[str]) -> List[str]:
    """Fix lines like: `env: { FOO: bar, BAZ: ${{ secret }} }` -> multiline map.
       Only touches single-line env maps that include `${{` to avoid false positives.
    """
    out = []
    for line in lines:
        m = re.match(r'^(\s*)env:\s*\{\s*([^}]+)\s*\}\s*$', line)
        if m and "${{" in line:
            base = m.group(1)
            inner = m.group(2)
            out.append(f"{base}env:\n")
            for part in inner.split(","):
                part = part.strip()
                if not part:
                    continue
                if ":" in part:
                    k, v = part.split(":", 1)
                    out.append(f"{base}  {k.strip()}: {v.strip()}\n")
        else:
            out.append(line)
    return out

def has_only_workflow_call(on_val) -> bool:
    """Reusable-only workflows (just `workflow_call`) shouldn't get dispatch."""
    if isinstance(on_val, dict):
        # exactly one key and it is workflow_call
        keys = set(on_val.keys())
        return keys == {"workflow_call"}
    return False

def ensure_dispatch(data) -> Tuple[bool, bool]:
    """Return (changed, dispatched_added) after ensuring workflow_dispatch exists if appropriate."""
    changed = False
    added = False
    onv = data.get("on")
    if onv is None:
        data["on"] = {"workflow_dispatch": {}}
        changed = True
        added = True
    elif isinstance(onv, str):
        data["on"] = {onv: None, "workflow_dispatch": {}}
        changed = True
        added = True
    elif isinstance(onv, list):
        merged = {k: None for k in onv}
        if "workflow_dispatch" not in merged:
            merged["workflow_dispatch"] = {}
            added = True
        data["on"] = merged
        changed = True
    elif isinstance(onv, dict):
        if not has_only_workflow_call(onv) and "workflow_dispatch" not in onv:
            onv["workflow_dispatch"] = {}
            changed = True
            added = True
    return changed, added

def main() -> int:
    fixed_files: List[str] = []
    added_dispatch: List[str] = []
    broken: List[str] = []

    for p in sorted(WF_DIR.glob("*.y*ml")):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        data, err = safe_load(txt)

        # Try a quick normalize if broken
        if err:
            lines = txt.splitlines(keepends=True)
            new_txt = "".join(normalize_inline_env(lines))
            if new_txt != txt:
                try:
                    yaml.safe_load(new_txt)
                    p.write_text(new_txt, encoding="utf-8")
                    fixed_files.append(p.name)
                    txt = new_txt
                    data, err = safe_load(txt)
                except Exception:
                    pass

        if err:
            broken.append(f"{p.name} · {type(err).__name__}")
            continue

        changed, added = ensure_dispatch(data)
        if changed:
            p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        if added:
            added_dispatch.append(p.name)

    # Outputs & summary
    summary = {
        "fixed_yaml": fixed_files,
        "added_dispatch": added_dispatch,
        "broken": broken,
        "total": len(list(WF_DIR.glob('*.y*ml')))
    }
    (OUTDIR / "SELF_HEAL_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    any_changes = bool(fixed_files or added_dispatch)
    (OUTDIR / "ANY_CHANGES").write_text("true" if any_changes else "false", encoding="utf-8")

    # GitHub step output (if available)
    gh_out = os.getenv("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"any_changes={'true' if any_changes else 'false'}\n")
            f.write(f"added_dispatch={','.join(added_dispatch)}\n")
            f.write(f"broken_count={len(broken)}\n")

    # Nice console group
    print("::group::Self-heal summary")
    print(json.dumps(summary, indent=2))
    print("::endgroup::")
    return 0

if __name__ == "__main__":
    sys.exit(main())
