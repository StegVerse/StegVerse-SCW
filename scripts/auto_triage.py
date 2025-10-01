#!/usr/bin/env python3
"""
Auto-triage using:
  - .steg/INTENT.yml (human intent & guardrails)
  - scripts/triage_rules.json (pattern rules)

Outputs:
  self_healing_out/AUTO_TRIAGE_PLAN.json
  self_healing_out/AUTO_TRIAGE_REPORT.md

Apply changes only when APPLY=1 is set:
  APPLY=1 python3 scripts/auto_triage.py
"""

from __future__ import annotations
import os, json, fnmatch, shutil, time, stat
from pathlib import Path
from typing import Dict, List, Any, Tuple

# ---------- Paths ----------
ROOT = Path(__file__).resolve().parents[1]
OUT  = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)

INTENT_YML = ROOT / ".steg" / "INTENT.yml"
TRIAGE_JSON = ROOT / "scripts" / "triage_rules.json"

# ---------- Helpers ----------
def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # requires PyYAML
    except Exception as e:
        # still run in read-only mode; caller should install PyYAML in workflow
        print(f"[auto_triage] WARNING: PyYAML not available; skipping parse of {path}", flush=True)
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"[auto_triage] WARNING: Failed to parse YAML: {path} -> {e}")
        return {}

def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[auto_triage] WARNING: Failed to parse JSON: {path} -> {e}")
        return {}

def list_files(base: Path) -> List[str]:
    ignore_dirs = {".git", "__pycache__", ".idea", ".vscode", "node_modules"}
    files: List[str] = []
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(base).as_posix()
        # skip ignored directories
        parts = rel.split("/")
        if any(seg in ignore_dirs for seg in parts):
            continue
        files.append(rel)
    return sorted(files)

def match_any(path: str, patterns: List[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns or [])

def ensure_dir(d: Path):
    d.mkdir(parents=True, exist_ok=True)

def write(path: Path, text: str):
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")

def is_text_file(p: Path) -> bool:
    try:
        p.read_text(encoding="utf-8")
        return True
    except Exception:
        return False

def attic_header(rel: str, intent: Dict[str, Any]) -> str:
    pol = (intent.get("attic_policy") or {})
    hdr = pol.get("header") or {}
    why = hdr.get("why", "Parked by auto-triage per INTENT")
    how = hdr.get("how_to_restore", "Move out of ATTIC/ and re-link imports if needed")
    ts  = time.strftime("%Y-%m-%d", time.gmtime())
    return f"# @attic\n# when: {ts}\n# why: {why}\n# how-to-restore: {how}\n# original-path: {rel}\n\n"

# ---------- Core ----------
def build_plan() -> Dict[str, Any]:
    intent = load_yaml(INTENT_YML)
    rules  = load_json(TRIAGE_JSON)

    files = list_files(ROOT)

    # From INTENT
    required_dirs  = set((intent.get("required") or {}).get("dirs", []) or [])
    required_files = set((intent.get("required") or {}).get("files", []) or [])
    forbidden_intent = list((intent.get("forbidden_globs") or []))
    attic_policy = (intent.get("attic_policy") or {})
    attic_exclude = set((attic_policy.get("exclude") or []))

    # From triage rules
    triage_attic   = ((rules.get("attic") or {}).get("move_if_globs") or [])
    triage_exclude = ((rules.get("attic") or {}).get("exclude_globs") or [])
    forbidden_rules = list((rules.get("remove_forbidden") or []))
    scaffold_dirs  = set(((rules.get("scaffold") or {}).get("dirs") or []))
    scaffold_files = set(((rules.get("scaffold") or {}).get("files") or []))

    # Union logic
    forbidden_globs = list(set(forbidden_intent) | set(forbidden_rules))
    attic_exclusions = list(set(triage_exclude) | attic_exclude)

    # Compute hits
    forbidden_hits = [f for f in files if match_any(f, forbidden_globs)]

    # Only move to ATTIC for explicit attic globs;
    # we do NOT consider "extras" here to avoid being aggressive.
    move_to_attic = [
        f for f in files
        if match_any(f, triage_attic)
        and not match_any(f, ["ATTIC/**"])
        and not match_any(f, list(attic_exclusions))
    ]

    # Scaffold from both INTENT(required) and rules(scaffold)
    missing_dirs = [d for d in (required_dirs | scaffold_dirs) if not (ROOT / d).exists()]
    missing_files = [f for f in (required_files | scaffold_files) if not (ROOT / f).exists()]

    # Keep: everything not being moved/removed
    to_remove = set(forbidden_hits)
    to_move   = set(move_to_attic)
    keep = [f for f in files if f not in to_remove and f not in to_move]

    plan = {
        "summary": {
            "files_scanned": len(files),
            "forbidden_hits": len(forbidden_hits),
            "to_attic": len(move_to_attic),
            "scaffold_dirs": len(missing_dirs),
            "scaffold_files": len(missing_files),
            "keep": len(keep),
        },
        "forbidden_globs": forbidden_globs,
        "attic_move_globs": triage_attic,
        "attic_exclusions": attic_exclusions,
        "required_dirs": sorted(list(required_dirs)),
        "required_files": sorted(list(required_files)),
        "scaffold_dirs": sorted(missing_dirs),
        "scaffold_files": sorted(missing_files),
        "remove_forbidden": sorted(forbidden_hits),
        "move_to_attic": sorted(move_to_attic),
        "keep": keep[:500],  # limit in report
    }
    return plan

def apply_plan(plan: Dict[str, Any], intent: Dict[str, Any]):
    # 1) scaffold dirs
    for d in plan.get("scaffold_dirs", []):
        target = ROOT / d
        ensure_dir(target)
        (target / ".gitkeep").write_text("", encoding="utf-8")

    # 2) scaffold files
    for f in plan.get("scaffold_files", []):
        p = ROOT / f
        ensure_dir(p.parent)
        if not p.exists():
            write(p, f"# TODO: scaffolded by auto_triage for {f}\n")

    # 3) remove forbidden
    for f in plan.get("remove_forbidden", []):
        p = ROOT / f
        try:
            # make writable if needed
            if p.exists():
                p.chmod(p.stat().st_mode | stat.S_IWUSR)
            p.unlink(missing_ok=True)
        except Exception as e:
            print(f"[auto_triage] WARN: remove failed: {f}: {e}")

    # 4) move to ATTIC (add header for text files)
    for f in plan.get("move_to_attic", []):
        src = ROOT / f
        if not src.exists():
            continue
        dst = ROOT / ("ATTIC/" + f)
        ensure_dir(dst.parent)
        try:
            if is_text_file(src):
                header = attic_header(f, intent)
                body   = src.read_text(encoding="utf-8", errors="ignore")
                write(dst, header + body)
                src.unlink(missing_ok=True)
            else:
                # binary or undecodable; move without header
                ensure_dir(dst.parent)
                dst.write_bytes(src.read_bytes())
                src.unlink(missing_ok=True)
        except Exception as e:
            print(f"[auto_triage] WARN: move to ATTIC failed for {f}: {e}")

def main():
    intent = load_yaml(INTENT_YML)
    plan = build_plan()

    # Write outputs
    (OUT / "AUTO_TRIAGE_PLAN.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    md = []
    md.append("# Auto-Triage Plan\n")
    s = plan["summary"]
    md.append(f"- Files scanned: **{s['files_scanned']}**")
    md.append(f"- Forbidden hits: **{s['forbidden_hits']}**")
    md.append(f"- To ATTIC: **{s['to_attic']}**")
    md.append(f"- Scaffold dirs: **{s['scaffold_dirs']}**")
    md.append(f"- Scaffold files: **{s['scaffold_files']}**\n")

    def sec(title: str, items: List[str]):
        md.append(f"## {title} ({len(items)})")
        if not items:
            md.append("- ✅ None\n")
            return
        for it in items[:200]:
            md.append(f"- `{it}`")
        md.append("")

    sec("Remove (forbidden)", plan.get("remove_forbidden", []))
    sec("Move to ATTIC", plan.get("move_to_attic", []))
    sec("Scaffold dirs", plan.get("scaffold_dirs", []))
    sec("Scaffold files", plan.get("scaffold_files", []))
    (OUT / "AUTO_TRIAGE_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    # Apply?
    if os.getenv("APPLY", "0") == "1":
        apply_plan(plan, intent)
        print("[auto_triage] Applied plan (APPLY=1).")
    else:
        print("[auto_triage] DRY RUN — set APPLY=1 to modify repo.")

if __name__ == "__main__":
    main()
