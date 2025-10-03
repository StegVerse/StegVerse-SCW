#!/usr/bin/env python3
"""
Auto-Fix Known Issues (conservative)
- Scans .github/workflows/*.yml,yaml
- Fixes common, safe issues:
  * Ensure workflow_dispatch exists
  * Normalize 'on:' to mapping, not list/string
  * Add security-events: write for CodeQL jobs using github/codeql-action/analyze
  * Add missing 'permissions: contents: read' at top-level if no permissions set
  * Ensure file newline, normalize trailing whitespace
- Honors optional JSON catalog at scripts/autopatch_catalog.json for extra regex line-edits.
- Dry-run by default. Use --apply or APPLY=1 to write changes.
Outputs: AUTO_FIX_REPORT.{json,md}
"""
import os, sys, json, re
from pathlib import Path
from copy import deepcopy

APPLY = ("--apply" in sys.argv) or (os.getenv("APPLY","0") == "1")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "self_healing_out"; OUT.mkdir(parents=True, exist_ok=True)
WF = ROOT / ".github" / "workflows"

try:
    from ruamel.yaml import YAML
except Exception:
    YAML = None  # We'll fall back to line-mode where possible

def load_catalog():
    p = ROOT / "scripts" / "autopatch_catalog.json"
    if not p.exists(): return {"line_edits": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"line_edits": []}

def ensure_mapping_on(on):
    """GitHub requires 'on' to be a mapping or a string; convert list->mapping with workflow_dispatch"""
    if isinstance(on, dict):
        return on
    if isinstance(on, str):
        return {on: {}}
    # list/None/etc → at least add workflow_dispatch
    return {"workflow_dispatch": {}}

def ensure_workflow_dispatch(on_map):
    if "workflow_dispatch" not in on_map:
        on_map["workflow_dispatch"] = {}
    return on_map

def ensure_permissions(yaml_obj):
    if "permissions" not in yaml_obj:
        yaml_obj["permissions"] = {"contents": "read"}
    return yaml_obj

def add_codeql_permission(yaml_obj):
    jobs = yaml_obj.get("jobs", {}) or {}
    changed = False
    for jn, job in jobs.items():
        if not isinstance(job, dict): continue
        steps = (job.get("steps") or [])
        uses_codeql = any(isinstance(s, dict) and str(s.get("uses","")).startswith("github/codeql-action/analyze@") for s in steps)
        if uses_codeql:
            # ensure job perms include security-events: write
            perms = job.get("permissions")
            if not isinstance(perms, dict):
                job["permissions"] = {"security-events": "write", "contents": "read"}
                changed = True
            elif perms.get("security-events") != "write":
                job["permissions"]["security-events"] = "write"
                if "contents" not in job["permissions"]:
                    job["permissions"]["contents"] = "read"
                changed = True
    return changed

def normalize_whitespace(text):
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    if not text.endswith("\n"): text += "\n"
    return text

def apply_line_catalog(text, line_edits):
    """Very conservative regex replaces from catalog."""
    for edit in line_edits:
        try:
            pattern = re.compile(edit["pattern"], re.MULTILINE)
            replace = edit.get("replace","")
            text2 = pattern.sub(replace, text)
            text = text2
        except Exception:
            continue
    return text

def process_yaml_file(p: Path, catalog):
    raw = p.read_text(encoding="utf-8", errors="ignore")
    before = raw
    changes = []
    # If ruamel.yaml available, do structure-aware edits
    if YAML:
        yaml = YAML()
        yaml.preserve_quotes = True
        try:
            obj = yaml.load(before)
            if obj is None: obj = {}
            if not isinstance(obj, dict): obj = {"on": obj}
        except Exception as e:
            # fall back to line mode only
            txt = apply_line_catalog(before, catalog.get("line_edits",[]))
            txt = normalize_whitespace(txt)
            wrote = (txt != before)
            return wrote, before, txt, ["line_edits_only (parse error)"]
        # on:
        on = obj.get("on")
        fixed_on = ensure_mapping_on(on)
        fixed_on = ensure_workflow_dispatch(fixed_on)
        if fixed_on != on:
            obj["on"] = fixed_on
            changes.append("normalized:on->mapping+workflow_dispatch")

        # top-level permissions
        orig = deepcopy(obj)
        obj = ensure_permissions(obj)
        if obj is not orig:
            changes.append("add:permissions.contents=read@top")

        # codeql job perms
        if add_codeql_permission(obj):
            changes.append("add:job.permissions.security-events=write (CodeQL)")

        # dump back
        from io import StringIO
        buf = StringIO()
        yaml.dump(obj, buf)
        txt = buf.getvalue()
        # catalog line edits + whitespace normalize
        txt = apply_line_catalog(txt, catalog.get("line_edits",[]))
        txt = normalize_whitespace(txt)
    else:
        # No ruamel → only line-mode
        txt = apply_line_catalog(before, catalog.get("line_edits",[]))
        txt = normalize_whitespace(txt)
        if txt != before:
            changes.append("line_edits_only")

    wrote = (txt != before)
    return wrote, before, txt, changes

def main():
    catalog = load_catalog()
    results = []
    if not WF.exists():
        report = {"ok": True, "files_seen": 0, "changed": 0, "note": "no workflows dir"}
        (OUT/"AUTO_FIX_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (OUT/"AUTO_FIX_REPORT.md").write_text("# Auto-Fix Report\n\n(no workflows)\n", encoding="utf-8")
        print("OK auto_fix (no workflows)")
        return

    changed_count = 0
    for p in sorted(list(WF.glob("*.y*ml"))):
        wrote, before, after, changes = process_yaml_file(p, catalog)
        if wrote and APPLY:
            p.write_text(after, encoding="utf-8")
        results.append({"path": p.as_posix(), "changed": bool(wrote and APPLY), "would_change": wrote and not APPLY, "changes": changes})

        if wrote: changed_count += 1

    rep = {
        "ok": True,
        "apply_mode": bool(APPLY),
        "files_seen": len(results),
        "changed": sum(1 for r in results if r["changed"]),
        "would_change": sum(1 for r in results if r["would_change"]),
        "results": results
    }
    (OUT/"AUTO_FIX_REPORT.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")

    # MD
    md = ["# Auto-Fix Report",
          f"- Apply mode: **{bool(APPLY)}**",
          f"- Files scanned: **{rep['files_seen']}**",
          f"- Changed: **{rep['changed']}**, Would change (dry): **{rep['would_change']}**",
          ""]
    if results:
        md.append("## File results")
        for r in results:
            flag = "✏️" if r["changed"] else ("🧪" if r["would_change"] else "—")
            md.append(f"- {flag} `{r['path']}` — changes: {', '.join(r['changes']) or 'none'}")
    else:
        md.append("(no workflow files)")
    (OUT/"AUTO_FIX_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("OK auto_fix_known_issues")

if __name__ == "__main__":
    main()
