#!/usr/bin/env python3
"""
repair_workflow_yaml.py

Pre-repair malformed workflow YAML so the normalizer can parse them later.

What it fixes (heuristics, idempotent):
  1) Converts accidental top-level `workflow:` to `on:` (only if no 'on:' exists).
  2) Replaces tabs with spaces; strips BOM and non-printables at file start.
  3) Ensures 'on:' is a mapping (fixes list form like `on:\n  - push` -> mapping).
  4) Lifts accidentally-indented top-level keys (name:, on:, jobs:, permissions:).
  5) If 'on:' is empty, injects `workflow_dispatch: {}`.
  6) Fixes common bracket/brace typos for `workflow_dispatch: []` -> `{}`.
Writes a markdown report and a marker file if anything changed.

This is *best effort*; it won't guess arbitrary broken YAML, but it handles the
real-world cases that break the “Run workflow” button.
"""

import argparse
import io
import os
import pathlib
import re
from typing import Tuple

import yaml

ROOT = pathlib.Path(".")
OUT_DIR = ROOT / "self_healing_out"
REPORT = OUT_DIR / "YAML_REPAIR_REPORT.md"
CHANGED = OUT_DIR / "YAML_REPAIR_CHANGED"

TOP_KEYS = ("name:", "on:", "workflow:", "jobs:", "permissions:", "env:", "concurrency:", "defaults:")

def read_text(p: pathlib.Path) -> str:
    t = p.read_text(encoding="utf-8", errors="ignore")
    # Drop BOM if present
    if t.startswith("\ufeff"):
        t = t.lstrip("\ufeff")
    # Normalize CRLF and tabs
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\t", "  ")
    return t

def lift_top_keys(txt: str) -> Tuple[str, bool]:
    """
    If file begins with accidental indentation for top-level keys, remove it.
    (e.g., '  on:\n    workflow_dispatch: {}' -> 'on:\n  workflow_dispatch: {}')
    """
    lines = txt.split("\n")
    changed = False
    # If the very first non-empty line starts with spaces and a known top key, de-indent all lines by that leading indent size (up to 4 spaces)
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        m = re.match(r"^(\s+)(\S.*)$", line)
        if not m:
            break
        indent = m.group(1)
        # only do this if the very first non-empty line is indented and is a top-level key
        if any(m.group(2).startswith(k) for k in TOP_KEYS):
            width = len(indent)
            # cap to a small value to avoid nuking valid structure
            width = min(width, 4)
            new_lines = []
            for L in lines:
                if L.startswith(" " * width):
                    new_lines.append(L[width:])
                else:
                    new_lines.append(L)
            changed = True
            return "\n".join(new_lines), changed
        break
    return txt, changed

def fix_workflow_to_on(txt: str) -> Tuple[str, bool]:
    """
    Replace a top-level 'workflow:' with 'on:' if the file has no 'on:' already.
    """
    if re.search(r"(?m)^\s*on\s*:", txt):
        return txt, False
    # Only replace if 'workflow:' appears at start of a line and looks like a root key
    if re.search(r"(?m)^\s*workflow\s*:\s*$", txt):
        txt2 = re.sub(r"(?m)^\s*workflow\s*:\s*$", "on:", txt)
        if txt2 != txt:
            return txt2, True
    return txt, False

def list_on_to_map_on(txt: str) -> Tuple[str, bool]:
    """
    Convert:
      on:
        - push
        - pull_request
    to:
      on:
        push: {}
        pull_request: {}
    """
    changed = False
    # Find 'on:' blocks
    m = re.search(r"(?m)^(on\s*:\s*\n(?:\s*-\s*\w+.*\n)+)", txt)
    if not m:
        return txt, changed

    block = m.group(1)
    # Extract event names
    events = re.findall(r"(?m)^\s*-\s*([a-zA-Z_]+)\s*$", block)
    if not events:
        return txt, changed

    # Build mapping block
    indent = "  "
    new_lines = ["on:"]
    for ev in events:
        new_lines.append(f"{indent}{ev}: {{}}")
    mapping = "\n".join(new_lines) + "\n"
    txt2 = txt.replace(block, mapping)
    if txt2 != txt:
        changed = True
    return txt2, changed

def ensure_dispatch(txt: str) -> Tuple[str, bool]:
    """
    If 'on:' exists but is empty or missing dispatch, add `workflow_dispatch: {}`
    """
    changed = False
    if not re.search(r"(?m)^\s*on\s*:", txt):
        return txt, changed

    # If empty mapping 'on: {}', expand and add dispatch
    txt2 = re.sub(r"(?m)^(\s*on\s*:\s*\{\s*\}\s*)$", r"on:\n  workflow_dispatch: {}", txt)
    if txt2 != txt:
        return txt2, True

    # If dispatch is in list or wrong bracket form
    txt3 = re.sub(r"(?m)^\s*workflow_dispatch\s*:\s*\[\s*\]\s*$", "workflow_dispatch: {}", txt2)
    if txt3 != txt2:
        changed = True

    # If no workflow_dispatch under on:, add it
    on_block_match = re.search(r"(?ms)^on\s*:\s*(.*?)(^\S|\Z)", txt3)
    if on_block_match:
        on_block = on_block_match.group(1)
        if not re.search(r"(?m)^\s*workflow_dispatch\s*:", on_block):
            # add one level indentation
            insertion = "  workflow_dispatch: {}"
            if on_block.strip() == "":
                new_block = "\n" + insertion + "\n"
            else:
                # append under existing 'on:' content
                if on_block.endswith("\n"):
                    new_block = on_block + insertion + "\n"
                else:
                    new_block = on_block + "\n" + insertion + "\n"
            txt3 = txt3.replace(on_block, new_block)
            changed = True

    return txt3, changed

def try_parse(txt: str) -> Tuple[bool, str]:
    try:
        yaml.safe_load(txt)
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def process_file(p: pathlib.Path, dry_run: bool) -> Tuple[bool, str]:
    original = read_text(p)
    txt = original
    changes = []

    # 1) de-BOM, tabs -> spaces, CRLF->LF (already done in read_text)
    if txt != original:
        changes.append("normalize-eols/tabs/bom")

    # 2) lift accidental indent of top keys
    txt, ch = lift_top_keys(txt)
    if ch: changes.append("lift-top-keys")

    # 3) fix `workflow:` -> `on:` if needed
    txt, ch = fix_workflow_to_on(txt)
    if ch: changes.append("workflow->on")

    # 4) `on:` list -> map
    txt, ch = list_on_to_map_on(txt)
    if ch: changes.append("on-list->map")

    # 5) ensure dispatch under on:
    txt, ch = ensure_dispatch(txt)
    if ch: changes.append("ensure-dispatch")

    ok, err = try_parse(txt)
    if not ok:
        # One last chance: if the very first key is indented, fully deindent first line
        m = re.match(r"^(\s+)(\S.*)", txt)
        if m:
            txt2 = re.sub(r"(?m)^  ", "", txt)  # remove 2-space indent across file
            ok2, err2 = try_parse(txt2)
            if ok2:
                txt = txt2
                changes.append("global-deindent")
                ok, err = True, ""

    if not ok:
        return False, f"UNFIXED: {err}"

    if dry_run:
        if txt != original:
            return True, f"would-fix: {', '.join(changes) or 'minor'}"
        return True, "ok"
    else:
        if txt != original:
            p.write_text(txt, encoding="utf-8")
            return True, f"fixed: {', '.join(changes) or 'minor'}"
        return True, "ok"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".github/workflows")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    changed_any = False

    wf_dir = pathlib.Path(args.dir)
    files = sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")))
    for p in files:
        ok, msg = process_file(p, args.dry_run)
        if not ok:
            rows.append(f"- ❌ `{p}` — {msg}")
        else:
            if msg.startswith("fixed:"):
                changed_any = True
                rows.append(f"- ✅ `{p}` — {msg}")
            else:
                rows.append(f"- ⏭ `{p}` — {msg}")

    md = io.StringIO()
    md.write("## Workflow YAML Repair Report\n\n")
    md.write(f"- Directory: `{wf_dir}`\n")
    md.write(f"- Dry run: `{args.dry_run}`\n\n")
    if rows:
        md.write("\n".join(rows) + "\n")
    REPORT.write_text(md.getvalue(), encoding="utf-8")

    if changed_any and not args.dry_run:
        CHANGED.write_text("changed", encoding="utf-8")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
