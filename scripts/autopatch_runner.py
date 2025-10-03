#!/usr/bin/env python3
"""
AutoPatch Runner (split + prune)
- Applies a patches manifest (YAML)
- Supports modes: ensure, replace, patch
- Writes a detailed report to self_healing_out/
- On success, optionally prunes completed items from the source manifest
- On failure/blocked, can append items to a deferred manifest

Usage:
  python3 scripts/autopatch_runner.py \
    --manifest .github/autopatch/patches.yml \
    --prune-success \
    --defer-file .github/autopatch/patches_deferred.yml

Notes:
- 'patch' mode appends the given block if the BEGIN/END markers are not found.
- 'ensure' creates the file if missing; if 'contents' present and file missing, writes it.
- 'replace' overwrites with 'contents' exactly.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
except Exception:
    raise SystemExit("Missing PyYAML/ruamel.yaml. Ensure the workflow installs YAML lib.")

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

def write_text(p: Path, txt: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")

def file_has_block(txt: str, begin_marker: str, end_marker: str) -> bool:
    return (begin_marker in txt) and (end_marker in txt)

def apply_patch_item(item: Dict[str, Any]) -> Tuple[str, str]:
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

    abs_path = ROOT / path
    exists = abs_path.exists()

    # Blockers you may add later (e.g., permissions, protected branches, etc.)
    # Right now, we assume we can write into the repo.
    try:
        if mode == "ensure":
            if exists:
                # If it exists, we don't overwrite unless explicitly asked
                return ("noop", f"{pid}: exists")
            else:
                # ensure=present -> create, possibly with contents
                if ensure == "present":
                    write_text(abs_path, contents or "")
                    return ("applied", f"{pid}: created {path}")
                else:
                    return ("skipped", f"{pid}: ensure={ensure} not handled")

        elif mode == "replace":
            write_text(abs_path, contents or "")
            return ("applied", f"{pid}: replaced {path}")

        elif mode == "patch":
            current = read_text(abs_path) if exists else ""
            # Try to auto-detect markers from the patch payload
            # Convention: first comment line contains 'BEGIN AUTOPATCH: <tag>' and paired END
            begin = None
            end = None
            for line in patch_block.splitlines():
                ls = line.strip()
                if "BEGIN AUTOPATCH" in ls and begin is None:
                    begin = ls
                if "END AUTOPATCH" in ls:
                    end = ls
            if not begin or not end:
                # Fallback: append if not present
                new_txt = current
                if patch_block and patch_block not in current:
                    new_txt = (current.rstrip() + "\n\n" + patch_block.strip() + "\n")
                    write_text(abs_path, new_txt)
                    return ("applied", f"{pid}: appended block (no markers)")
                return ("noop", f"{pid}: block already present (no markers)")
            # With markers: only append if missing
            if file_has_block(current, begin, end):
                return ("noop", f"{pid}: markers already present")
            new_txt = (current.rstrip() + "\n\n" + patch_block.strip() + "\n")
            write_text(abs_path, new_txt)
            return ("applied", f"{pid}: appended marker block")

        else:
            return ("skipped", f"{pid}: unknown mode {mode}")

    except Exception as e:
        return ("error", f"{pid}: exception {e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--prune-success", action="store_true")
    ap.add_argument("--defer-file", default="")
    args = ap.parse_args()

    manifest_path = ROOT / args.manifest
    manifest = load_yaml(manifest_path)
    patches: List[Dict[str, Any]] = manifest.get("patches", []) or []

    results = {
        "manifest": str(manifest_path),
        "prune_success": bool(args.prune_success),
        "defer_file": args.defer_file or None,
        "summary": {"applied": 0, "noop": 0, "skipped": 0, "blocked": 0, "error": 0},
        "items": [],
    }

    deferred: List[Dict[str, Any]] = []
    remaining: List[Dict[str, Any]] = []

    for item in patches:
        status, msg = apply_patch_item(item)
        results["summary"][status] = results["summary"].get(status, 0) + 1
        results["items"].append({
            "id": item.get("id"),
            "path": item.get("path"),
            "mode": item.get("mode"),
            "status": status,
            "message": msg
        })

        if status in ("applied", "noop"):
            # treat noop as satisfied (already present)
            # -> can be pruned if flag is on
            if not args.prune_success:
                remaining.append(item)
        elif status in ("blocked", "error"):
            deferred.append(item)
        else:
            # skipped stays for later re-run in the same manifest
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
        "",
        "## Summary",
        *(f"- {k}: **{v}**" for k, v in results["summary"].items()),
        "",
        "## Items",
    ]
    for it in results["items"]:
        lines.append(f"- **{it['status'].upper():7}** — {it['id']} → `{it['path']}` — {it['message']}")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Handle prune + defer
    changed = False
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

    # Indicate outcome for the workflow
    print(json.dumps({"changed_manifests": changed, "deferred_count": len(deferred)}, indent=2))

if __name__ == "__main__":
    main()
