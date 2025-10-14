#!/usr/bin/env python3
"""
Normalize all workflow files so GitHub recognizes the manual "Run workflow" button:

- Ensure top-level `on:` is a mapping (dict), converting from list/string if needed.
- Inject `workflow_dispatch: {}` at the root (unless the file is reusable-only with only `workflow_call`).
- Skip files that fail YAML parse (report them).
- Preserve key order (PyYAML safe_dump with sort_keys=False).
- Write a markdown report to self_healing_out/NORMALIZE_REPORT.md
- Emit GitHub Actions outputs: `changed=true|false`.
"""

import argparse, pathlib, sys, io, json
from typing import Tuple, Dict, Any, List

import yaml

ROOT = pathlib.Path(".")
WF_DIR_DEFAULT = ROOT / ".github" / "workflows"
OUT_DIR = ROOT / "self_healing_out"
REPORT_MD = OUT_DIR / "NORMALIZE_REPORT.md"

def load_yaml(path: pathlib.Path):
    try:
        text = path.read_text(encoding="utf-8")
        return yaml.safe_load(text), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )

def to_mapping(on_val) -> Dict[str, Any]:
    """Normalize `on` into a dict: supports string or list of strings."""
    if on_val is None:
        return {}
    if isinstance(on_val, dict):
        return dict(on_val)
    if isinstance(on_val, list):
        out = {}
        for ev in on_val:
            if isinstance(ev, str):
                out[ev] = {}
        return out
    if isinstance(on_val, str):
        return {on_val: {}}
    return {}

def reusable_only(on_map: Dict[str, Any]) -> bool:
    keys = list(on_map.keys())
    return len(keys) == 1 and keys[0] == "workflow_call"

def ensure_dispatch(d: dict) -> Tuple[bool, str]:
    """
    Ensure root d['on'] is mapping and includes workflow_dispatch, unless reusable-only.
    Returns (changed?, reason)
    """
    if not isinstance(d, dict):
        return False, "not a mapping at root"

    on_map = to_mapping(d.get("on"))
    changed = False
    reason_msgs: List[str] = []

    # If file is reusable-only, skip
    if reusable_only(on_map):
        return False, "reusable-only (workflow_call)"

    # Inject dispatch if missing
    if "workflow_dispatch" not in on_map:
        on_map["workflow_dispatch"] = {}
        changed = True
        reason_msgs.append("added workflow_dispatch")

    # Replace root on:
    if d.get("on") != on_map:
        d["on"] = on_map
        # mark changed only if this replacement is a type normalization
        if not changed:
            changed = True
            reason_msgs.append("normalized on: structure")

    reason = ", ".join(reason_msgs) if reason_msgs else "no-op"
    return changed, reason

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(WF_DIR_DEFAULT), help="Workflows directory")
    ap.add_argument("--dry-run", action="store_true", help="Only report, do not modify files")
    args = ap.parse_args()

    wf_dir = pathlib.Path(args.dir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    changed_any = False
    rows = []
    errors = []

    for p in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))):
        data, err = load_yaml(p)
        if err:
            errors.append((str(p), err))
            rows.append(f"- ❌ `{p}` — YAML parse error: `{err}`")
            continue

        changed, reason = ensure_dispatch(data)
        if changed and not args.dry_run:
            p.write_text(dump_yaml(data), encoding="utf-8")
            changed_any = True
            rows.append(f"- ✅ `{p}` — {reason}")
        else:
            icon = "⏭" if not changed else "🧪"
            note = reason if changed else "no change needed"
            rows.append(f"- {icon} `{p}` — {note}")

    # Write report
    md = io.StringIO()
    md.write("## Workflow Dispatch Normalization Report\n\n")
    md.write(f"- Directory: `{wf_dir}`\n")
    md.write(f"- Dry run: `{args.dry_run}`\n\n")
    if rows:
        md.write("\n".join(rows) + "\n\n")
    if errors:
        md.write("### Parse errors\n")
        for path, err in errors:
            md.write(f"- `{path}` → `{err}`\n")
        md.write("\n")
    REPORT_MD.write_text(md.getvalue(), encoding="utf-8")

    # Emit output for the workflow step
    gha_out = ROOT / os.environ.get("GITHUB_OUTPUT", "GITHUB_OUTPUT_NOT_SET")
    # If GITHUB_OUTPUT is not available (local run), just print.
    out_line = f"changed={'true' if changed_any else 'false'}"
    if gha_out.exists():
        with gha_out.open("a", encoding="utf-8") as f:
            f.write(out_line + "\n")
    else:
        print(out_line)

if __name__ == "__main__":
    import os
    sys.exit(main())
