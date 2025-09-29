#!/usr/bin/env python3
"""
validate_and_fix.py  (extended)
Scans .github/workflows/*.yml|yaml, auto-fixes common GitHub Actions pitfalls, and
writes reports into self_healing_out/.

Existing fixes kept:
  1) Escape python shebang in heredocs: '#!/usr/bin/env python3' → '#\\!/usr/bin/env python3'
  2) Quote boolean defaults for workflow_dispatch inputs: true/false → "true"/"false"
  3) Wrap bare 'secrets.NAME' in 'if:' lines: secrets.X → ${{ secrets.X }}
  4) Normalize heredoc terminators (strip trailing spaces on 'PY'/'EOF')

New fixes added:
  5) Strip UTF-8 BOM if present
  6) Convert leading TABs to two spaces (indentation only; leaves in-line tabs alone)
  7) Ensure each job has 'runs-on' (default: 'ubuntu-latest') if missing
  8) Ensure boolean defaults under workflow_dispatch inputs are strings at YAML level too
  9) Normalize line endings to '\n' and ensure file ends with newline
 10) Optional: auto-quote unquoted 'on: workflow_dispatch' input defaults that are numbers

Two-phase approach:
  - Text-phase regex fixes (safe, minimal)
  - YAML-phase structural fixes (PyYAML). If we change structure, we re-dump YAML.
    We write a .bak once per file when applying structural changes, to be safe.

CLI:
  python scripts/validate_and_fix.py            # dry run
  python scripts/validate_and_fix.py --apply    # apply in-place

Outputs:
  self_healing_out/WORKFLOW_FIX_REPORT.json
  self_healing_out/WORKFLOW_FIX_REPORT.md
"""

import os
import re
import sys
import json
import codecs
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / ".github" / "workflows"
OUT    = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)

# ---------- Helpers ----------

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

def load_yaml_docs(text: str) -> List[Any]:
    import yaml
    return list(yaml.safe_load_all(text))

def dump_yaml_docs(docs: List[Any]) -> str:
    import yaml
    # Default Dumper may reorder keys; acceptable for CI normalization.
    # Keep multi-doc support:
    return "\n---\n".join(
        [yaml.safe_dump(doc, sort_keys=True, default_flow_style=False).rstrip() for doc in docs if doc is not None]
    ) + "\n"

# ---------- Text-phase regexes ----------

SHEBANG_RE      = re.compile(r'^(?P<lead>\s*)(#!\/usr\/bin\/env\s+python3)\s*$', re.MULTILINE)
BOOL_INPUT_RE   = re.compile(r'^(?P<lead>\s*default:\s*)(true|false)\s*$', re.IGNORECASE | re.MULTILINE)
IF_SECRETS_RE   = re.compile(r'^(?P<lead>\s*if:\s*)(?P<expr>.*)$', re.MULTILINE)
BARE_SECRET     = re.compile(r'(?<!\{\{\s*)\bsecrets\.([A-Z0-9_]+)\b(?!\s*\}\})', re.IGNORECASE)
HEREDOC_ENDS    = re.compile(r'^(?P<lead>\s*)(PY|EOF)\s+$', re.MULTILINE)
LEADING_TABS_RE = re.compile(r'^(?P<ind>\t+)', re.MULTILINE)  # only at line start

def strip_bom(text: str) -> Tuple[str, bool]:
    if text.startswith(codecs.BOM_UTF8.decode('utf-8')):
        return text.lstrip(codecs.BOM_UTF8.decode('utf-8')), True
    return text, False

def normalize_endings(text: str) -> Tuple[str, bool]:
    new = text.replace('\r\n', '\n').replace('\r', '\n')
    if not new.endswith('\n'):
        new += '\n'
    return new, (new != text)

def fix_text_phase(original: str) -> Tuple[str, Dict[str, int]]:
    fixed = original
    changed_counts = {
        "bom_stripped": 0,
        "shebang": 0,
        "bool_inputs": 0,
        "if_secrets": 0,
        "heredoc_trim": 0,
        "leading_tabs_to_spaces": 0,
        "normalized_endings": 0,
    }

    # 5) Strip BOM
    fixed2, bom = strip_bom(fixed)
    if bom:
        changed_counts["bom_stripped"] += 1
        fixed = fixed2

    # 6) Convert leading tabs to two spaces
    def tabs_to_spaces(m):
        tabs = m.group('ind')
        changed_counts["leading_tabs_to_spaces"] += 1
        return '  ' * len(tabs)
    fixed = LEADING_TABS_RE.sub(tabs_to_spaces, fixed)

    # 1) Escape shebangs in heredocs
    def esc_shebang(m):
        changed_counts["shebang"] += 1
        lead = m.group("lead") or ""
        return f"{lead}#\\!/usr/bin/env python3"
    fixed = SHEBANG_RE.sub(esc_shebang, fixed)

    # 2) Quote boolean defaults on inputs
    def quote_bool(m):
        changed_counts["bool_inputs"] += 1
        lead = m.group("lead")
        val  = m.group(2).lower()
        return f'{lead}"{val}"'
    fixed = BOOL_INPUT_RE.sub(quote_bool, fixed)

    # 3) Wrap bare secrets inside "if:" only
    def wrap_if_line(m):
        lead = m.group("lead") or ""
        expr = m.group("expr") or ""
        before = expr
        expr = BARE_SECRET.sub(r'${{ secrets.\1 }}', expr)
        if expr != before:
            changed_counts["if_secrets"] += 1
        return f"{lead}{expr}"
    fixed = IF_SECRETS_RE.sub(lambda m: f"{m.group('lead')}if: {wrap_if_line(m)}", fixed)

    # 4) Trim heredoc end tokens
    def trim_end(m):
        changed_counts["heredoc_trim"] += 1
        lead = m.group("lead") or ""
        tok  = m.group(2)
        return f"{lead}{tok}\n"
    fixed = HEREDOC_ENDS.sub(trim_end, fixed)

    # 9) Normalize line endings; final newline
    fixed3, norm = normalize_endings(fixed)
    if norm:
        changed_counts["normalized_endings"] += 1
        fixed = fixed3

    return fixed, changed_counts

# ---------- YAML-phase structural fixes ----------

def coerce_inputs_defaults_to_strings(doc: Dict) -> int:
    """
    For on.workflow_dispatch.inputs.*.default ensure strings
    """
    if not isinstance(doc, dict): return 0
    on = doc.get("on") or doc.get("On") or doc.get("ON")
    if not on: return 0
    changed = 0

    # 'on' can be a dict, list or string
    if isinstance(on, dict):
        wd = on.get("workflow_dispatch")
        if isinstance(wd, dict):
            inputs = wd.get("inputs")
            if isinstance(inputs, dict):
                for k, v in inputs.items():
                    if isinstance(v, dict) and "default" in v:
                        d = v["default"]
                        if isinstance(d, (bool, int, float)):
                            v["default"] = str(d).lower() if isinstance(d, bool) else str(d)
                            changed += 1
    return changed

def ensure_runs_on_for_jobs(doc: Dict) -> int:
    """
    Ensure each job has 'runs-on'. If missing, set 'ubuntu-latest'.
    """
    if not isinstance(doc, dict): return 0
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict): return 0
    changed = 0
    for name, job in jobs.items():
        if isinstance(job, dict):
            if not any(k in job for k in ("runs-on", "runs_on", "runsOn")):
                job["runs-on"] = "ubuntu-latest"
                changed += 1
    return changed

def try_structural_fixes(yaml_text: str) -> Tuple[str, Dict[str, int], bool, str]:
    """
    Parse YAML, apply structural fixes, re-dump.
    Returns (new_text, stats, valid, error)
    """
    try:
        docs = load_yaml_docs(yaml_text)
    except Exception as e:
        return yaml_text, {"struct_load_error": 1}, False, str(e)

    stats = {"inputs_defaults_quoted": 0, "job_runs_on_added": 0}
    changed = False

    for i, doc in enumerate(docs):
        if not isinstance(doc, dict):
            continue
        stats["inputs_defaults_quoted"] += coerce_inputs_defaults_to_strings(doc)
        stats["job_runs_on_added"] += ensure_runs_on_for_jobs(doc)

    if any(v > 0 for v in stats.values()):
        changed = True

    if changed:
        new_text = dump_yaml_docs(docs)
    else:
        new_text = yaml_text

    valid, err = yaml_valid(new_text)
    return new_text, stats, valid, err

# ---------- Orchestrator per file ----------

def process_file(p: Path, apply: bool) -> Dict:
    original = p.read_text(encoding="utf-8", errors="ignore")

    # Validate before
    before_valid, before_err = yaml_valid(original)

    # Text phase
    text_fixed, text_stats = fix_text_phase(original)
    text_changed = (text_fixed != original)

    # YAML structural phase
    post_yaml, yaml_stats, after_valid, after_err = try_structural_fixes(text_fixed)
    struct_changed = (post_yaml != text_fixed)

    changed_any = text_changed or struct_changed

    if apply and changed_any:
        # Write a .bak once per apply run for safety if major structural changed
        if struct_changed:
            bak = p.with_suffix(p.suffix + ".bak")
            if not bak.exists():
                bak.write_text(original, encoding="utf-8")
        p.write_text(post_yaml, encoding="utf-8")

    return {
        "path": str(p.relative_to(ROOT)),
        "changed": changed_any,
        "text_phase_changed": text_changed,
        "struct_phase_changed": struct_changed,
        "before_valid": before_valid,
        "before_error": before_err,
        "after_valid": after_valid,
        "after_error": after_err,
        "text_stats": text_stats,
        "yaml_stats": yaml_stats,
    }

# ---------- Main ----------

def main():
    apply = "--apply" in sys.argv
    ensure_pyyaml()

    files = []
    if WF_DIR.exists():
        files = [p for p in WF_DIR.glob("*.y*ml") if p.is_file()]
    files.sort()

    results = [process_file(p, apply) for p in files]
    summary = {
        "files": len(results),
        "changed": sum(1 for r in results if r["changed"]),
        "invalid_before": sum(1 for r in results if not r["before_valid"]),
        "invalid_after": sum(1 for r in results if not r["after_valid"]),
        "applied": apply,
        "job_runs_on_added": sum(r["yaml_stats"].get("job_runs_on_added", 0) for r in results),
        "inputs_defaults_quoted": sum(r["yaml_stats"].get("inputs_defaults_quoted", 0) for r in results),
    }

    OUT_JSON = OUT / "WORKFLOW_FIX_REPORT.json"
    OUT_MD   = OUT / "WORKFLOW_FIX_REPORT.md"

    OUT_JSON.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")

    lines = []
    lines.append("# Workflow Fix Report\n")
    lines.append(f"- Files scanned: **{summary['files']}**")
    lines.append(f"- Files changed: **{summary['changed']}** (apply={summary['applied']})")
    lines.append(f"- Invalid before: **{summary['invalid_before']}**")
    lines.append(f"- Invalid after: **{summary['invalid_after']}**")
    lines.append(f"- Jobs missing runs-on fixed: **{summary['job_runs_on_added']}**")
    lines.append(f"- Inputs defaults normalized: **{summary['inputs_defaults_quoted']}**\n")

    def fmt_stats(d: Dict[str,int]) -> str:
        return ", ".join([f"{k}:{v}" for k, v in d.items() if v]) or "none"

    for r in results:
        lines.append(f"## {r['path']}")
        lines.append(f"- changed: **{r['changed']}** (text={r['text_phase_changed']}, struct={r['struct_phase_changed']})")
        lines.append(f"- YAML valid before: **{r['before_valid']}**")
        if not r['before_valid']: lines.append(f"  - error: `{r['before_error']}`")
        lines.append(f"- YAML valid after: **{r['after_valid']}**")
        if not r['after_valid']: lines.append(f"  - error: `{r['after_error']}`")
        lines.append(f"- text fixes: {fmt_stats(r['text_stats'])}")
        lines.append(f"- yaml fixes:  {fmt_stats(r['yaml_stats'])}\n")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    # Exit 1 if still invalid after fixes (so CI can flag remaining issues)
    if summary["invalid_after"] > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
