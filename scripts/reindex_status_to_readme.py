#!/usr/bin/env python3
"""
scripts/reindex_status_to_readme.py

Reads .github/taskops/ledger.jsonl and updates README.md between:
  <!-- reindex-status:start --> ... <!-- reindex-status:end -->

If the markers are missing, the workflow will add them (see workflow step).
"""

import json, pathlib, datetime, sys

LEDGER = pathlib.Path(".github/taskops/ledger.jsonl")
README = pathlib.Path("README.md")
START = "<!-- reindex-status:start -->"
END = "<!-- reindex-status:end -->"

def latest_reindex():
    if not LEDGER.exists():
        return None
    last = None
    with LEDGER.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except Exception:
                continue
            if j.get("job") == "autopatch-reindex":
                last = j
    return last

def format_line(j):
    ts = j.get("ts", "")
    run_id = j.get("run_id", "")
    branch = j.get("branch", "")
    wf_present = j.get("workflow_present", "unknown")
    dispatch_ok = j.get("dispatch_ok", "n/a")
    nudged = j.get("nudged", "false")
    target_wf = j.get("target_workflow", "autopatch-apply.yml")

    # Normalize booleans-as-strings
    def yesno(v):
        s = str(v).lower()
        if s in ("true", "1", "yes", "ok"):
            return "true"
        if s in ("false", "0", "no", "n/a", "na"):
            return s
        return s

    wf_present = yesno(wf_present)
    dispatch_ok = yesno(dispatch_ok)
    nudged = yesno(nudged)

    return (
        f"Last Reindex: 📦 present={wf_present} | 🚀 dispatch={dispatch_ok} | 🔁 nudged={nudged} "
        f"— run #{run_id} @ {ts} on `{branch}` (target: `{target_wf}`)"
    )

def update_readme():
    if not README.exists():
        # nothing to do safely
        print("README.md not found; skipping")
        return 0

    text = README.read_text(encoding="utf-8")

    if START not in text or END not in text:
        # Markers must exist; the workflow creates them before calling this script.
        print("Markers not found; skipping update (ensure step should add them).")
        return 0

    head, rest = text.split(START, 1)
    mid, tail = rest.split(END, 1)

    j = latest_reindex()
    if not j:
        new_block = "No reindex runs logged yet."
    else:
        new_block = format_line(j)

    new_text = f"{head}{START}\n{new_block}\n{END}{tail}"
    if new_text != text:
        README.write_text(new_text, encoding="utf-8")
        print("README updated with latest reindex status.")
        return 1
    print("README already up to date.")
    return 0

if __name__ == "__main__":
    changed = update_readme()
    # Exit 0 so workflow continues even if nothing changed
    sys.exit(0)
