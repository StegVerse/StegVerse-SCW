#!/usr/bin/env python3
"""
Normalize all workflow files so GitHub shows the 'Run workflow' button:

- Ensure top-level `on:` is a mapping (dict), converting from list/string if needed.
- Inject `workflow_dispatch: {}` at the root (unless the file is reusable-only with only `workflow_call`).
- Skip files that fail YAML parse (report them).
- Preserve key order (sort_keys=False).
- Write a markdown report to self_healing_out/NORMALIZE_REPORT.md.
- If any file changed, create self_healing_out/NORMALIZE_CHANGED as a marker.
"""

import argparse
import io
import os
import pathlib
from typing import Any, Dict, Tuple, List

import yaml

ROOT = pathlib.Path(".")
WF_DIR_DEFAULT = ROOT / ".github" / "workflows"
OUT_DIR = ROOT / "self_healing_out"
REPORT_MD = OUT_DIR / "NORMALIZE_REPORT.md"
CHANGED_MARKER = OUT_DIR / "NORMALIZE_CHANGED"


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
        return False, "root is not a mapping"

    on_map = to_mapping(d.get("on"))
    # Skip reusable-only files
    if reusable_only(on_map):
        return False, "reusable-only (workflow_call)"

    changed = False
    reasons: List[str] = []

    if "workflow_dispatch" not in on_map:
        on_map["workflow_dispatch"] = {}
        changed = True
        reasons.append("added workflow_dispatch")

    if d.get("on") != on_map:
        d["on"] = on_map
        if not changed:
            changed = True
        reasons.append("normalized 'on:' structure")

    return changed, ", ".join(reasons) if reasons else "no-op"


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

    files = sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")))
    for p in files:
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
            note = reason if changed else "no change needed"
            rows.append(f"- ⏭ `{p}` — {note}")

    # Report
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

    # Marker for the workflow to decide whether to commit
    if changed_any:
        CHANGED_MARKER.write_text("changed", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
