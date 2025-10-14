#!/usr/bin/env python3
"""
Repair GitHub workflow YAML files:
- Normalizes line endings/tabs/trailing spaces
- Tries to parse with PyYAML; if parse succeeds, can also normalize `on:`
- Writes report to self_healing_out/YAML_REPAIR_REPORT.md
- Touches self_healing_out/YAML_REPAIR_CHANGED when any file changed
Usage:
  repair_workflow_yaml.py --dir .github/workflows [--dry-run]
"""
import argparse, pathlib, re, sys, io, textwrap
from typing import Tuple
import yaml

OUTDIR = pathlib.Path("self_healing_out")
OUTDIR.mkdir(parents=True, exist_ok=True)
REPORT = OUTDIR / "YAML_REPAIR_REPORT.md"
CHANGED_FLAG = OUTDIR / "YAML_REPAIR_CHANGED"

def normalize_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("\t", "  ")
    # strip trailing spaces
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    # ensure final newline
    if not s.endswith("\n"):
        s += "\n"
    return s

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

def is_reusable_only(on_map: dict) -> bool:
    if not on_map: return False
    keys = list(on_map.keys())
    return len(keys) == 1 and keys[0] == "workflow_call"

def safe_dump(data) -> str:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )

def attempt_fix(path: pathlib.Path, dry_run: bool) -> Tuple[bool, str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    normalized = normalize_text(raw)

    changed_via_norm = (normalized != raw)
    parse_err1 = None
    try:
        data = yaml.safe_load(normalized)
    except Exception as e:
        parse_err1 = e
        data = None

    # If still failing, we can't do structural fixes safely.
    if data is None:
        msg = f"❌ Parse failed: {path} — {type(parse_err1).__name__}: {parse_err1}"
        if changed_via_norm and not dry_run:
            # write normalized (it might already help future passes)
            path.write_text(normalized, encoding="utf-8")
            return True, msg + " (wrote normalized text)"
        return changed_via_norm, msg

    # Data parsed — we can normalize `on:` to a mapping
    on_val = data.get("on", None)
    on_map = to_mapping_on(on_val)
    if on_map != on_val:
        data["on"] = on_map

    new_text = safe_dump(data)
    changed = (new_text != normalized)
    if (changed or changed_via_norm) and not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return (changed or changed_via_norm), f"✅ Repaired/normalized: {path}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".github/workflows", help="Workflows directory")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    wfdir = pathlib.Path(args.dir)
    results = []
    changed_any = False

    if not wfdir.exists():
        print(f"[repair] no directory: {wfdir}")
        return 0

    for p in sorted(list(wfdir.glob("*.y*ml"))):
        try:
            changed, note = attempt_fix(p, args.dry_run)
            results.append(note)
            changed_any = changed_any or changed
        except Exception as e:
            results.append(f"❌ Exception on {p}: {e}")

    REPORT.write_text(
        "# Workflow YAML Repair Report\n\n" + "\n".join(f"- {r}" for r in results) + "\n",
        encoding="utf-8",
    )
    if changed_any and not args.dry_run:
        CHANGED_FLAG.write_text("changed\n", encoding="utf-8")

    print(f"[repair] Done. Report -> {REPORT}")
    if changed_any:
        print("[repair] Changes were made.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
