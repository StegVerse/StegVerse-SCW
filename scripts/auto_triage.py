#!/usr/bin/env python3
"""
Auto-Triage
- Reads REPO_DIFF.json from repo_audit
- Plans: remove_forbidden, move_to_attic (extras), scaffold_dirs, scaffold_files
- If APPLY=1 (or --apply), performs actions and writes headers in ATTIC files
Outputs: AUTO_TRIAGE_PLAN.json, AUTO_TRIAGE_REPORT.md
"""
import os, json, time, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "self_healing_out"; OUT.mkdir(parents=True, exist_ok=True)

def load_json(p):
    p = ROOT / p
    if not p.exists(): return {}
    return json.loads(p.read_text(encoding="utf-8"))

def attic_header(rel, why="Parked by auto-triage"):
    ts = time.strftime("%Y-%m-%d", time.gmtime())
    return f"# @attic\n# when: {ts}\n# why: {why}\n# how-to-restore: move file out of ATTIC/, re-link imports if needed\n\n"

def main():
    apply = ("--apply" in sys.argv) or (os.getenv("APPLY","0") == "1")
    diff = load_json("self_healing_out/REPO_DIFF.json")
    required_missing = diff.get("required_missing", []) or []
    dir_missing = diff.get("dir_missing", []) or []
    extras = diff.get("extras", []) or []
    forb = diff.get("forbidden_hits", []) or []

    plan = {
        "remove_forbidden": sorted(forb),
        "move_to_attic": sorted([e for e in extras if not e.startswith(("ATTIC/","docs/","tests/"))]),
        "scaffold_dirs": sorted(dir_missing),
        "scaffold_files": sorted(required_missing),
        "keep": []
    }
    (OUT/"AUTO_TRIAGE_PLAN.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    md = ["# Auto-Triage Plan"]
    def sec(t, lst):
        md.append(f"\n## {t} ({len(lst)})")
        md += ([f"- `{p}`" for p in lst] or ["- ✅ None"])
    sec("To Remove (forbidden)", plan["remove_forbidden"])
    sec("To ATTIC (extras)", plan["move_to_attic"])
    sec("Scaffold Dirs", plan["scaffold_dirs"])
    sec("Scaffold Files", plan["scaffold_files"])
    (OUT/"AUTO_TRIAGE_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if not apply:
        print("DRY RUN"); return

    # Apply
    for d in plan["scaffold_dirs"]:
        (ROOT/d).mkdir(parents=True, exist_ok=True)
        (ROOT/d/".gitkeep").write_text("", encoding="utf-8")

    for f in plan["scaffold_files"]:
        p = ROOT/f; p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists(): p.write_text(f"# TODO: add content for {f}\n", encoding="utf-8")

    for f in plan["remove_forbidden"]:
        try: (ROOT/f).unlink(missing_ok=True)
        except Exception: pass

    for f in plan["move_to_attic"]:
        src = ROOT/f
        if not src.exists(): continue
        dst = ROOT/("ATTIC/"+f)
        dst.parent.mkdir(parents=True, exist_ok=True)
        try: body = src.read_text(encoding="utf-8", errors="ignore")
        except Exception: body = ""
        dst.write_text(attic_header(f) + body, encoding="utf-8")
        src.unlink(missing_ok=True)

    print("Applied auto-triage changes.")

if __name__ == "__main__":
    main()
