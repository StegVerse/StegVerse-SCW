#!/usr/bin/env python3
"""
YAML Corrector v2 — precision + sweep
- Fix known recurring issues
- Normalize formatting
- Validate syntax
- Write reports & ledgers
"""

import os, re, json, sys, hashlib, datetime
from pathlib import Path
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"
OUT = ROOT / "self_healing_out"; OUT.mkdir(parents=True, exist_ok=True)

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

# Known regex rules (precision fixes)
RULES = [
    {"pattern": r"TIMEOUT_SEC:(\S+)", "replace": r"TIMEOUT_SEC: \1", "desc": "normalize spacing"},
    {"pattern": r"::set-output", "replace": "echo \"$name=$value\" >> $GITHUB_OUTPUT", "desc": "migrate set-output"},
]

def sha256(text: str): return hashlib.sha256(text.encode()).hexdigest()[:12]

def correct_file(path: Path, apply=False):
    text = path.read_text(encoding="utf-8")
    orig = text
    applied = []
    # Regex rules
    for rule in RULES:
        new, n = re.subn(rule["pattern"], rule["replace"], text)
        if n > 0:
            applied.append(rule["desc"])
            text = new
    # Try parse/roundtrip with ruamel.yaml
    try:
        data = yaml.load(text)
        if data:
            from io import StringIO
            buf = StringIO()
            yaml.dump(data, buf)
            text = buf.getvalue()
    except Exception as e:
        applied.append(f"parse-error: {e}")
    if apply and text != orig:
        path.write_text(text, encoding="utf-8")
    return {"file": path.as_posix(), "changed": text != orig, "applied": applied, "hash": sha256(text)}

def main():
    apply = "--apply" in sys.argv or os.getenv("APPLY") == "true"
    results = []
    if not WF.exists():
        print("No workflows dir."); return
    for f in sorted(WF.glob("*.y*ml")):
        results.append(correct_file(f, apply=apply))
    report = {
        "repo": os.getenv("GITHUB_REPOSITORY", ROOT.name),
        "generated_at": datetime.datetime.utcnow().isoformat()+"Z",
        "apply": apply,
        "results": results
    }
    (OUT/"YAML_CORRECTOR_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# YAML Corrector Report", ""]
    for r in results:
        mark = "✅" if not r["changed"] else "✏️"
        lines.append(f"- {mark} `{r['file']}` — rules: {', '.join(r['applied']) or 'none'}")
    (OUT/"YAML_CORRECTOR_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("Report written.")
if __name__ == "__main__":
    main()
