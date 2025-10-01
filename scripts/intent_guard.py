#!/usr/bin/env python3
"""
Enforce human intent from .steg/INTENT.yml.
- Fails (exit 1) if required files missing or forbidden globs present.
- Emits a machine and human report to self_healing_out/INTENT_GUARD.*
- Computes a risk level for the current diff and prints a recommendation.
"""
import sys, os, json, fnmatch, subprocess
from pathlib import Path

try:
    import yaml
except ImportError:
    print("intent_guard: installing PyYAML...", file=sys.stderr)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)
CFG = ROOT / ".steg" / "INTENT.yml"

def load_cfg():
    if not CFG.exists():
        return {}
    import yaml
    return yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}

def glob_any(path:str, patterns:list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)

def git_files_changed():
    # Changed vs. HEAD^ if present, else full tree
    try:
        base = subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=ROOT).decode().strip()
        lines = subprocess.check_output(["git", "diff", "--name-only", "HEAD^..HEAD"], cwd=ROOT).decode().splitlines()
        if lines: return sorted(lines)
    except Exception:
        pass
    lines = subprocess.check_output(["git", "ls-files"], cwd=ROOT).decode().splitlines()
    return sorted(lines)

def main():
    cfg = load_cfg()
    errors = []
    warn   = []
    changed = git_files_changed()

    # required
    req_dirs  = set(cfg.get("required", {}).get("dirs", []))
    req_files = set(cfg.get("required", {}).get("files", []))
    for d in req_dirs:
        if not (ROOT/d).exists():
            errors.append(f"Required dir missing: {d}")
    for f in req_files:
        if not (ROOT/f).exists():
            errors.append(f"Required file missing: {f}")

    # forbidden
    forb = cfg.get("forbidden_globs", [])
    hits = []
    for p in ROOT.rglob("*"):
        if p.is_file():
            rel = p.relative_to(ROOT).as_posix()
            if glob_any(rel, forb):
                hits.append(rel)
    if hits:
        errors.append(f"Forbidden items present: {', '.join(hits)}")

    # risk classification
    high_paths = set(cfg.get("review_paths", []))
    risk = "low"
    if any(glob_any(c, list(high_paths)) for c in changed):
        risk = "high"
    elif any(c.startswith(("scripts/", ".github/workflows/")) for c in changed):
        risk = "medium"

    policy = cfg.get("risk_policy", {}).get("levels", {})
    rec = {
        "risk": risk,
        "auto_apply": bool(policy.get(risk, {}).get("auto_apply", False)),
        "require_review_from": policy.get(risk, {}).get("require_review_from", []),
        "require_two_maintainers": bool(policy.get(risk, {}).get("require_two_maintainers", False)),
    }

    report = {
        "intent_file": str(CFG),
        "changed": changed,
        "errors": errors,
        "warnings": warn,
        "recommendation": rec,
    }
    (OUT/"INTENT_GUARD.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = [ "# INTENT Guard Report",
           f"- Risk level: **{risk}**",
           f"- Auto-apply: **{ 'yes' if rec['auto_apply'] else 'no' }**",
           "" ]
    if errors:
        md.append("## Errors")
        md += [f"- {e}" for e in errors]
    else:
        md.append("## Errors\n- ✅ None")
    md.append("\n## Changed files")
    md += [f"- `{c}`" for c in changed[:200]] or ["- (none)"]
    (OUT/"INTENT_GUARD.md").write_text("\n".join(md), encoding="utf-8")

    # exit code
    if errors:
        sys.exit(1)
    else:
        print(json.dumps(rec), flush=True)

if __name__ == "__main__":
    main()
