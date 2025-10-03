#!/usr/bin/env python3
import os, re, json, textwrap, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / ".github" / "workflows"
OUT = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)

RID = os.getenv("RID", f"RID-auto-{os.getenv('GITHUB_RUN_ID','local')}")
TASK = os.getenv("TASK", "STEG-unknown")

def load_manifest():
    p = ROOT / "patches" / "manifest.json"
    if not p.exists():
        return {"version": 1, "defaults": {}, "workflows": {}, "fixes": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"version": 1, "defaults": {}, "workflows": {}, "fixes": {}, "_error": f"bad manifest: {e}"}

def list_workflows():
    if not WF_DIR.exists():
        return []
    return sorted([p for p in WF_DIR.glob("*.y*ml") if p.is_file()])

def has_block(txt, needle):
    return needle in txt

def ensure_permissions(txt, perms):
    # if there is a 'permissions:' block, leave it; otherwise inject after 'on:' or at top
    if re.search(r'^\s*permissions\s*:\s*$', txt, flags=re.M):
        return txt, False
    block = "permissions:\n" + "\n".join([f"  {p}" for p in perms]) + "\n"
    # Try to insert after 'on:' stanza
    m = re.search(r'^\s*on\s*:(?:.|\n)*?\n\n', txt, flags=re.M)
    if m:
        insert_at = m.end()
        new = txt[:insert_at] + block + txt[insert_at:]
    else:
        new = block + "\n" + txt
    return new, True

def ensure_concurrency(txt, group, cancel):
    if re.search(r'^\s*concurrency\s*:', txt, flags=re.M):
        return txt, False
    block = textwrap.dedent(f"""\
    concurrency:
      group: {group}
      cancel-in-progress: {"true" if cancel else "false"}
    """)
    # Insert after permissions if present else after on:
    m = re.search(r'^\s*permissions\s*:(?:.|\n)*?\n\n', txt, flags=re.M)
    if not m:
        m = re.search(r'^\s*on\s*:(?:.|\n)*?\n\n', txt, flags=re.M)
    if m:
        insert_at = m.end()
        new = txt[:insert_at] + block + txt[insert_at:]
    else:
        new = block + "\n" + txt
    return new, True

def ensure_push_triggers(txt, paths):
    # add the common push trigger paths if not present
    if ".github/trigger" in txt:
        return txt, False
    block = textwrap.dedent("""\
    \n  # File-based triggers (mobile friendly)\n  push:\n    branches: [ "main" ]\n    paths:\n""")
    for p in paths:
        block += f'      - "{p}"\n'
    # naive: append under 'on:'; if no 'on:' create it
    if re.search(r'^\s*on\s*:\s*$', txt, flags=re.M):
        return txt.replace("on:\n", "on:\n" + block), True
    if "on:" in txt:
        # Insert after first 'on:' line
        new = re.sub(r'on:\s*\n', "on:\n" + block, txt, count=1)
        return new, True
    # prepend minimal on:
    new = "on:\n" + block + "\n" + txt
    return new, True

READ_INTENT_STEP = textwrap.dedent("""\
      - name: Read run intent (RID/TASK)
        shell: bash
        run: |
          set -e
          INTENT_FILE="$(ls .github/trigger/**/run.* 2>/dev/null | head -n1 || true)"
          RID_IN=""
          TASK_IN=""
          if [ -n "$INTENT_FILE" ]; then
            RID_IN="$(grep -E '^(rid|RID):\\s*' "$INTENT_FILE" | head -n1 | sed 's/^[^:]*:\\s*//')"
            TASK_IN="$(grep -E '^(task|TASK):\\s*' "$INTENT_FILE" | head -n1 | sed 's/^[^:]*:\\s*//')"
          fi
          echo "RID=${RID_IN:-%RID%}" >> $GITHUB_ENV
          echo "TASK=${TASK_IN:-%TASK%}" >> $GITHUB_ENV
""")

def ensure_read_intent_step(txt):
    if "Read run intent (RID/TASK)" in txt:
        return txt, False
    # Insert after first checkout step
    pat = r'(-\s+uses:\s+actions/checkout@v[0-9]+[\s\S]*?\n)'
    m = re.search(pat, txt)
    if not m:
        return txt, False
    block = READ_INTENT_STEP.replace("%RID%", RID).replace("%TASK%", TASK)
    insert_at = m.end()
    return txt[:insert_at] + "\n" + block + txt[insert_at:], True

UPLOAD_SWEEP_STEP = textwrap.dedent("""\
      - name: Upload Sweep (reusable)
        if: always()
        uses: ./.github/workflows/_reusables/upload-sweep.yml
        with:
          name: universal_fixit_sweep
          base_dir: self_healing_out
          files: |
            SWEEP_REPORT.json
            SWEEP_REPORT.md
          create_placeholder: true
""")

def ensure_upload_sweep_step(txt):
    if "Upload Sweep (reusable)" in txt:
        return txt, False
    # add before final artifact upload if we can find one
    m = re.search(r'-\s+name:\s+Upload\s+Supercheck\s+Bundle[\s\S]*?uses:\s+actions/upload-artifact@', txt)
    if m:
        insert_at = m.start()
        return txt[:insert_at] + UPLOAD_SWEEP_STEP + txt[insert_at:], True
    return txt + "\n" + UPLOAD_SWEEP_STEP, True

def rewrite_printf_to_heredoc(txt):
    # Replace fragile printf multi-line blocks writing files with a safe heredoc
    # Matches patterns similar to: printf '%s\\n' 'line1' 'line2' > path
    changed = False
    def repl(m):
        nonlocal changed
        body = m.group(1)
        target = m.group(2)
        # Convert each '...' item to lines
        lines = re.findall(r"'([^']*)'", body)
        heredoc = "<<'EOF_CORR'\n" + "\n".join(lines) + "\nEOF_CORR\n"
        changed = True
        return f"cat {heredoc} > {target}"
    new = re.sub(r"printf\s+'%s\\n'\s+((?:'[^']*'\s*)+)\s*>\s*([^\s]+)", repl, txt)
    return new, changed

def apply_fixes(name, yaml_text, manifest):
    changed = []
    notes = []

    fixes = manifest.get("fixes", {})
    defaults = manifest.get("defaults", {})

    # YAML-002
    if "YAML-002" in fixes and defaults.get("ensure_permissions"):
        new, did = ensure_permissions(yaml_text, defaults["ensure_permissions"])
        if did: changed.append("YAML-002"); yaml_text = new

    # YAML-003
    if "YAML-003" in fixes and defaults.get("ensure_concurrency"):
        cc = defaults["ensure_concurrency"]
        group = cc.get("group", "${workflow}-${ref}")
        cancel = bool(cc.get("cancel-in-progress", True))
        new, did = ensure_concurrency(yaml_text, group, cancel)
        if did: changed.append("YAML-003"); yaml_text = new

    # YAML-006
    if "YAML-006" in fixes and defaults.get("add_push_triggers"):
        new, did = ensure_push_triggers(yaml_text, defaults["add_push_triggers"])
        if did: changed.append("YAML-006"); yaml_text = new

    # workflow-specific
    wf_rules = manifest.get("workflows", {}).get(name, {})

    if wf_rules.get("ensure_read_intent"):
        new, did = ensure_read_intent_step(yaml_text)
        if did: changed.append("YAML-004"); yaml_text = new

    if wf_rules.get("ensure_upload_sweep"):
        new, did = ensure_upload_sweep_step(yaml_text)
        if did: changed.append("YAML-005"); yaml_text = new

    # YAML-001 always last (content-level transform)
    if "YAML-001" in fixes:
        new, did = rewrite_printf_to_heredoc(yaml_text)
        if did: changed.append("YAML-001"); yaml_text = new

    return yaml_text, changed, notes

def detect_name(yaml_text, path):
    m = re.search(r'^\s*name\s*:\s*(.+)$', yaml_text, flags=re.M)
    if m:
        return re.sub(r'#.*$', '', m.group(1)).strip()
    return Path(path).stem

def main():
    manifest = load_manifest()
    report = {
        "rid": RID,
        "task": TASK,
        "summary": {"files": 0, "changed_files": 0, "fixes": {}, "errors": 0},
        "results": []
    }
    for wf in list_workflows():
        txt = wf.read_text(encoding="utf-8", errors="ignore")
        name = detect_name(txt, wf)
        new_txt, fixes_applied, _ = apply_fixes(name.lower().replace(" ", "_"), txt, manifest)
        changed = fixes_applied != []
        if changed:
            wf.write_text(new_txt, encoding="utf-8")
            for f in fixes_applied:
                report["summary"]["fixes"][f] = report["summary"]["fixes"].get(f, 0) + 1
        report["results"].append({
            "path": wf.as_posix(),
            "name": name,
            "changed": changed,
            "fixes": fixes_applied
        })
    report["summary"]["files"] = len(report["results"])
    report["summary"]["changed_files"] = sum(1 for r in report["results"] if r["changed"])

    (OUT / "AUTOPATCH_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = [f"# AutoPatch Report",
          f"- RID: `{RID}`",
          f"- TASK: `{TASK}`",
          f"- Files scanned: **{report['summary']['files']}**",
          f"- Files changed: **{report['summary']['changed_files']}**",
          "",
          "## Fix counts"]
    if report["summary"]["fixes"]:
        for k,v in sorted(report["summary"]["fixes"].items()):
            md.append(f"- {k}: {v}")
    else:
        md.append("- none")
    md.append("\n## Per-file results")
    for r in report["results"]:
        fixes = ", ".join(r["fixes"]) if r["fixes"] else "—"
        md.append(f"- `{r['path']}` — {'CHANGED' if r['changed'] else 'OK'} — fixes: {fixes}")
    (OUT / "AUTOPATCH_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))

if __name__ == "__main__":
    main()
