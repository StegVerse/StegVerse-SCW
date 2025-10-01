#!/usr/bin/env python3
import re, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / ".github" / "workflows"
OUT = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)

RULES = json.loads((ROOT / ".github" / "remediations" / "KNOWN_ISSUES.json").read_text(encoding="utf-8"))
REPORT = {"detected": [], "fixed": [], "skipped": [], "errors": []}

# Prebuilt safe heredoc block we’ll inject when we find YAML-001
SAFE_BLOCK = r"""      - name: Seed corrector shim if missing
        shell: bash
        run: |
          set -e
          mkdir -p scripts self_healing_out
          if [ ! -f scripts/yaml_corrector_v2.py ] && [ -f scripts/yaml_corrector.py ]; then
            cat > scripts/yaml_corrector_v2.py <<'PY'
#!/usr/bin/env python3
import runpy, sys, pathlib
me = pathlib.Path(__file__).resolve()
legacy = me.with_name("yaml_corrector.py")
if not legacy.exists():
    print("ERROR: scripts/yaml_corrector.py not found", file=sys.stderr)
    sys.exit(1)
argv = ["yaml_corrector.py"]
if "--apply" in sys.argv:
    argv.append("--apply")
sys.argv = argv
runpy.run_path(str(legacy), run_name="__main__")
PY
            chmod +x scripts/yaml_corrector_v2.py
          fi
"""

def load(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def save(p: Path, content: str):
    p.write_text(content, encoding="utf-8")

def fix_yaml_001(text: str) -> str:
    """
    Replace the fragile printf-based shim block with a heredoc block.
    We look for the step name and a subsequent printf '%s\\n' \\ chain.
    """
    # Match the whole step beginning at the name line through to the end of the run block.
    step_start = re.compile(r"(?m)^\s*- name:\s*Seed corrector shim if missing\s*$")
    pos = None
    m = step_start.search(text)
    if not m:
        return text  # no block
    pos = m.start()

    # From start, capture until the next step start or end of file
    next_step = re.compile(r"(?m)^\s*- name:\s+")
    tail = text[pos:]
    m2 = next_step.search(tail, 1)
    block = tail if not m2 else tail[:m2.start()]
    if not re.search(r"printf\s+'%s\\n'\s*\\", block):
        return text  # nothing fragile inside

    # Replace entire block with SAFE_BLOCK (keep original indentation)
    indent = re.match(r"(\s*)", block).group(1)
    safe = ("\n".join(indent + line if line else "" for line in SAFE_BLOCK.splitlines())).rstrip() + "\n"
    before = text[:pos]
    after = text[pos+len(block):]
    return before + safe + after

def main():
    for issue in RULES.get("issues", []):
        if issue.get("id") != "YAML-001":
            continue
        regex = re.compile(issue["match"]["regex"])
        for wf in sorted(WF_DIR.glob("*.yml")):
            try:
                t = load(wf)
                if not regex.search(t):
                    continue
                REPORT["detected"].append({"id": issue["id"], "file": str(wf.relative_to(ROOT))})
                new = fix_yaml_001(t)
                if new != t:
                    save(wf, new)
                    REPORT["fixed"].append({"id": issue["id"], "file": str(wf.relative_to(ROOT))})
                else:
                    REPORT["skipped"].append({"id": issue["id"], "file": str(wf.relative_to(ROOT)), "reason": "pattern not fully matched"})
            except Exception as e:
                REPORT["errors"].append({"file": str(wf), "error": str(e)})

    # Write machine + human reports
    (OUT / "AUTO_FIX_REPORT.json").write_text(json.dumps(REPORT, indent=2), encoding="utf-8")
    md = ["# Auto-Fix Report", ""]
    for k in ("detected", "fixed", "skipped", "errors"):
        md.append(f"## {k.title()} ({len(REPORT[k])})")
        for row in REPORT[k]:
            md.append(f"- `{row.get('file','')}` — {json.dumps({kk:vv for kk,vv in row.items() if kk!='file'})}")
        md.append("")
    (OUT / "AUTO_FIX_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print("OK auto-fix")

if __name__ == "__main__":
    sys.exit(main() or 0)
