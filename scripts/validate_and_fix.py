#!/usr/bin/env python3
"""
validate_and_fix.py
- Scans .github/workflows/*.yml|yaml
- Detects common GitHub Actions YAML gotchas
- Applies safe text fixes (optional --apply)
- Writes a human report and machine JSON to self_healing_out/

Fixes implemented:
1) Heredoc Python shebang inside YAML:  '#!/usr/bin/env python3' -> '#\\!/usr/bin/env python3'
2) Inputs booleans must be strings:     'default: true/false'    -> 'default: "true"/"false"'
3) Bare 'secrets.NAME' in if/expr:      'secrets.X'              -> '${{ secrets.X }}'  (only in "if:" lines)
4) Trim whitespace on heredoc terminators: lines equal to 'PY'/'EOF' get stripped to exactly that token

Validation:
- Attempts to import PyYAML; if missing, installs it on the fly (runner-safe).
- safe_load_all() to catch syntax errors post-fix.

Usage:
  python scripts/validate_and_fix.py            # dry run, no changes
  python scripts/validate_and_fix.py --apply    # apply changes in-place
"""
import os, re, sys, json, subprocess
from pathlib import Path
from typing import List, Tuple, Dict

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / ".github" / "workflows"
OUT    = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)

def ensure_pyyaml():
    try:
        import yaml  # noqa: F401
        return
    except Exception:
        subprocess.run([sys.executable, "-m", "pip", "install", "PyYAML", "--quiet"], check=False)

def yaml_valid(text: str) -> Tuple[bool, str]:
    try:
        import yaml
        list(yaml.safe_load_all(text))
        return True, ""
    except Exception as e:
        return False, str(e)

SHEBANG_RE   = re.compile(r'^(?P<lead>\s*)(#!\/usr\/bin\/env\s+python3)\s*$', re.MULTILINE)
BOOL_INPUT_RE = re.compile(r'^(?P<lead>\s*default:\s*)(true|false)\s*$', re.IGNORECASE | re.MULTILINE)
IF_SECRETS_RE = re.compile(r'^(?P<lead>\s*if:\s*)(?P<expr>.*)$', re.MULTILINE)
BARE_SECRET   = re.compile(r'(?<!\{\{\s*)\bsecrets\.([A-Z0-9_]+)\b(?!\s*\}\})', re.IGNORECASE)
HEREDOC_ENDS  = re.compile(r'^(?P<lead>\s*)(PY|EOF)\s+$', re.MULTILINE)

def fix_text(original: str) -> Tuple[str, Dict[str, int]]:
    fixed = original
    stats = {"shebang":0, "bool_inputs":0, "if_secrets":0, "heredoc_trim":0}

    # 1) Escape Python shebang inside heredocs
    def esc_shebang(m):
        stats["shebang"] += 1
        lead = m.group("lead") or ""
        return f"{lead}#\\!/usr/bin/env python3"
    fixed = SHEBANG_RE.sub(esc_shebang, fixed)

    # 2) Quote boolean defaults under workflow_dispatch inputs
    def quote_bool(m):
        stats["bool_inputs"] += 1
        lead = m.group("lead")
        val  = m.group(2).lower()
        return f'{lead}"{val}"'
    fixed = BOOL_INPUT_RE.sub(quote_bool, fixed)

    # 3) Wrap bare secrets.X in ${{ }} inside "if:" lines only
    def wrap_if(line_expr: re.Match) -> str:
        lead = line_expr.group("lead") or ""
        expr = line_expr.group("expr") or ""
        before = expr
        expr = BARE_SECRET.sub(r'${{ secrets.\1 }}', expr)
        if expr != before:
            stats["if_secrets"] += 1
        return f"{lead}{expr}" if lead.strip().startswith("if:") else f"{lead}if: {expr}"
    fixed = IF_SECRETS_RE.sub(lambda m: f"{m.group('lead')}if: {wrap_if(m)}", fixed)

    # 4) Clean heredoc terminators (ensure exactly 'PY' or 'EOF')
    def trim_end(m):
        stats["heredoc_trim"] += 1
        lead = m.group("lead") or ""
        tok  = m.group(2)
        return f"{lead}{tok}\n"
    fixed = HEREDOC_ENDS.sub(trim_end, fixed)

    return fixed, stats

def process_file(p: Path, apply: bool) -> Dict:
    text = p.read_text(encoding="utf-8", errors="ignore")
    before_valid, err_before = yaml_valid(text)

    fixed, stats = fix_text(text)
    after_valid, err_after = yaml_valid(fixed)

    changed = (fixed != text)
    if apply and changed:
        p.write_text(fixed, encoding="utf-8")

    return {
        "path": str(p.relative_to(ROOT)),
        "changed": changed,
        "before_valid": before_valid,
        "before_error": err_before,
        "after_valid": after_valid,
        "after_error": err_after,
        "stats": stats,
    }

def main():
    apply = "--apply" in sys.argv
    ensure_pyyaml()

    files = [p for p in WF_DIR.glob("*.y*ml") if p.is_file()]
    files.sort()

    results = [process_file(p, apply) for p in files]
    summary = {
        "files": len(results),
        "changed": sum(1 for r in results if r["changed"]),
        "invalid_before": sum(1 for r in results if not r["before_valid"]),
        "invalid_after": sum(1 for r in results if not r["after_valid"]),
        "applied": apply,
    }
    OUT_JSON = OUT / "WORKFLOW_FIX_REPORT.json"
    OUT_MD   = OUT / "WORKFLOW_FIX_REPORT.md"

    OUT_JSON.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")

    lines = []
    lines.append("# Workflow Fix Report\n")
    lines.append(f"- Files scanned: **{summary['files']}**")
    lines.append(f"- Files changed: **{summary['changed']}** (apply={summary['applied']})")
    lines.append(f"- Invalid before: **{summary['invalid_before']}**")
    lines.append(f"- Invalid after: **{summary['invalid_after']}**\n")
    for r in results:
        lines.append(f"## {r['path']}")
        lines.append(f"- changed: **{r['changed']}**")
        lines.append(f"- YAML valid before: **{r['before_valid']}**")
        if not r['before_valid']: lines.append(f"  - error: `{r['before_error']}`")
        lines.append(f"- YAML valid after: **{r['after_valid']}**")
        if not r['after_valid']: lines.append(f"  - error: `{r['after_error']}`")
        stats = ", ".join([f"{k}:{v}" for k,v in r["stats"].items() if v])
        lines.append(f"- fixes applied: {stats or 'none'}\n")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    # Non-zero exit if still invalid after fixes (so CI can catch)
    if summary["invalid_after"] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
