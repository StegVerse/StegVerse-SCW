#!/usr/bin/env python3
"""
AutoPatch Runner (split + prune, with preconditions + dry-run)
- Applies a patches manifest (YAML)
- Modes: ensure, replace, patch
- Preconditions: requires_files[], requires_dirs[]  (if unmet -> 'blocked')
- Dry-run: --dry-run (shows what WOULD change, still writes a report)
- Writes a detailed report to self_healing_out/
- On success, can prune completed items from the source manifest
- On blocked/error, can defer items into another manifest

Usage:
  python3 scripts/autopatch_runner.py \
    --manifest .github/autopatch/patches.yml \
    --prune-success \
    --defer-file .github/autopatch/patches_deferred.yml \
    [--dry-run]

Notes:
- 'patch' mode appends the given block if the BEGIN/END markers are not found.
- 'ensure' creates the file if missing; if 'contents' present and file missing, writes it.
- 'replace' overwrites with 'contents' exactly.
- Markers are auto-detected from lines containing 'BEGIN AUTOPATCH' and 'END AUTOPATCH'.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
except Exception:
    raise SystemExit("Missing PyYAML (or ruamel). Ensure the workflow installs a YAML lib.")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)

def load_yaml(p: Path) -> Dict[str, Any]:
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def dump_yaml(p: Path, data: Dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""

def write_text(p: Path, txt: str, dry_run: bool) -> None:
    if dry_run:
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")

def file_has_block(txt: str, begin_marker: str, end_marker: str) -> bool:
    return (begin_marker in txt) and (end_marker in txt)

def unmet_preconditions(item: Dict[str, Any]) -> List[str]:
    msgs = []
    req_files = item.get("requires_files") or []
    req_dirs  = item.get("requires_dirs") or []
    for rf in req_files:
        if not (ROOT / rf).exists():
            msgs.append(f"missing file: {rf}")
    for rd in req_dirs:
        if not (ROOT / rd).exists():
            msgs.append(f"missing dir:  {rd}")
    return msgs

def apply_patch_item(item: Dict[str, Any], dry_run: bool) -> Tuple[str, str]:
    """
    Returns (status, message)
    status one of: 'applied', 'skipped', 'blocked', 'noop', 'error'
    """
    pid = item.get("id", "<no-id>")
    path = item.get("path")
    mode = (item.get("mode") or "ensure").lower()
    ensure = (item.get("ensure") or "present").lower()
    contents = item.get("contents", "")
    patch_block = item.get("patch", "")

    if not path:
        return ("error", f"{pid}: missing 'path'")

    # Preconditions
    blockers = unmet_preconditions(item)
    if blockers:
        return ("blocked", f"{pid}: preconditions unmet -> {', '.join(blockers)}")

    abs_path = ROOT / path
    exists = abs_path.exists()

    try:
        if mode == "ensure":
            if exists:
                return ("noop", f"{pid}: exists")
            if ensure == "present":
                write_text(abs_path, contents or "", dry_run)
                return ("applied", f"{pid}: created {path}" + (" (dry-run)" if dry_run else ""))
            return ("skipped", f"{pid}: ensure={ensure} not handled")

        elif mode == "replace":
            write_text(abs_path, contents or "", dry_run)
            return ("applied", f"{pid}: replaced {path}" + (" (dry-run)" if dry_run else ""))

        elif mode == "patch":
            current = read_text(abs_path) if exists else ""
            begin = None; end = None
            for line in patch_block.splitlines():
                ls = line.strip()
                if "BEGIN AUTOPATCH" in ls and begin is None:
                    begin = ls
                if "END AUTOPATCH" in ls:
                    end = ls
            if not begin or not end:
                if patch_block and patch_block not in current:
                    new_txt = (current.rstrip() + "\n\n" + patch_block.strip() + "\n")
                    write_text(abs_path, new_txt, dry_run)
                    return ("applied", f"{pid}: appended block (no markers)" + (" (dry-run)" if dry_run else ""))
                return ("noop", f"{pid}: block already present (no markers)")
            if file_has_block(current, begin, end):
                return ("noop", f"{pid}: markers already present")
            new_txt = (current.rstrip() + "\n\n" + patch_block.strip() + "\n")
            write_text(abs_path, new_txt, dry_run)
            return ("applied", f"{pid}: appended marker block" + (" (dry-run)" if dry_run else ""))

        else:
            return ("skipped", f"{pid}: unknown mode {mode}")

    except Exception as e:
        return ("error", f"{pid}: exception {e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--prune-success", action="store_true")
    ap.add_argument("--defer-file", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manifest_path = ROOT / args.manifest
    manifest = load_yaml(manifest_path)
    patches: List[Dict[str, Any]] = manifest.get("patches", []) or []

    results = {
        "manifest": str(manifest_path),
        "prune_success": bool(args.prune_success),
        "defer_file": args.defer_file or None,
        "dry_run": bool(args.dry_run),
        "summary": {"applied": 0, "noop": 0, "skipped": 0, "blocked": 0, "error": 0},
        "items": [],
    }

    deferred: List[Dict[str, Any]] = []
    remaining: List[Dict[str, Any]] = []

    for item in patches:
        status, msg = apply_patch_item(item, dry_run=args.dry_run)
        results["summary"][status] = results["summary"].get(status, 0) + 1
        results["items"].append({
            "id": item.get("id"),
            "path": item.get("path"),
            "mode": item.get("mode"),
            "status": status,
            "message": msg
        })

        if status in ("applied", "noop"):
            if not args.prune_success:
                remaining.append(item)
        elif status in ("blocked", "error"):
            deferred.append(item)
        else:
            remaining.append(item)

    # Write reports
    OUT_JSON = OUT / "AUTOPATCH_REPORT.json"
    OUT_MD   = OUT / "AUTOPATCH_REPORT.md"
    OUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")

    lines = [
        "# AutoPatch Report",
        f"- Manifest: `{results['manifest']}`",
        f"- Prune success: `{results['prune_success']}`",
        f"- Defer file: `{results['defer_file'] or '—'}`",
        f"- Dry run: `{results['dry_run']}`",
        "",
        "## Summary",
        *(f"- {k}: **{v}**" for k, v in results["summary"].items()),
        "",
        "## Items",
    ]
    for it in results["items"]:
        lines.append(f"- **{it['status'].upper():7}** — {it['id']} → `{it['path']}` — {it['message']}")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Handle prune + defer (only if not dry-run)
    changed = False
    if not args.dry_run:
        if args.prune_success:
            manifest_pruned = dict(manifest)
            manifest_pruned["patches"] = remaining
            if remaining != patches:
                dump_yaml(manifest_path, manifest_pruned)
                changed = True

        if args.defer_file and deferred:
            defer_path = ROOT / args.defer_file
            existing = load_yaml(defer_path)
            if not existing:
                existing = {"version": 1, "patches": []}
            existing_patches = existing.get("patches", []) or []
            existing_patches.extend(deferred)
            existing["patches"] = existing_patches
            dump_yaml(defer_path, existing)
            changed = True

    print(json.dumps({"changed_manifests": changed, "deferred_count": len(deferred)}, indent=2))

if __name__ == "__main__":
    main()
