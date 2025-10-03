#!/usr/bin/env python3
"""
AutoPatch: apply centralized YAML workflow patches safely & idempotently.

- Reads patches/manifest.json for patch rules (targets + snippets + operations)
- Loads snippets from patches/snippets/*.yml
- Applies changes with ruamel.yaml (preserves order/comments reasonably)
- Writes a report in self_healing_out/AUTOPATCH_REPORT.{json,md}
- Modes:
    --apply      : write changes to disk
    --dry-run    : (default) only report proposed changes

Operations supported (per target file):
  - ensure_on_triggers: merge/ensure 'on:' sections (dispatch/push/schedule)
  - ensure_permissions: merge/ensure top-level 'permissions'
  - ensure_concurrency: set/update concurrency group+cancel
  - ensure_job_guard  : add job-level if: guard expression
  - ensure_steps      : ensure named steps exist (insert or update)
  - ensure_uses       : ensure a reusable step exists (by "name" and "uses")

Notes:
  - Idempotent: if a section already matches, nothing changes.
  - Targets can be explicit or globs: ".github/workflows/*.yml"
"""

import sys, json, fnmatch, hashlib, argparse
from pathlib import Path
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / ".github" / "workflows"
SNIP_DIR = ROOT / "patches" / "snippets"
OUT_DIR = ROOT / "self_healing_out"
OUT_DIR.mkdir(parents=True, exist_ok=True)

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=2, offset=2)

def load_manifest():
    p = ROOT / "patches" / "manifest.json"
    if not p.exists():
        return {"patches": []}
    return json.loads(p.read_text(encoding="utf-8"))

def load_snippet(name):
    p = SNIP_DIR / f"{name}.yml"
    if not p.exists():
        return None
    return yaml.load(p.read_text(encoding="utf-8"))

def merge_map(dst, src):
    """Deep merge mapping into dst (create keys if missing)."""
    if src is None: return dst
    if dst is None: return src
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            merge_map(dst[k], v)
        else:
            dst[k] = v
    return dst

def ensure_on_triggers(doc, spec):
    # spec snippet will be merged under 'on'
    doc.setdefault('on', {})
    merge_map(doc['on'], spec)
    return True

def ensure_permissions(doc, spec):
    doc.setdefault('permissions', {})
    merge_map(doc['permissions'], spec)
    return True

def ensure_concurrency(doc, spec):
    # { group: "...", cancel-in-progress: true }
    doc['concurrency'] = doc.get('concurrency') or {}
    merge_map(doc['concurrency'], spec)
    return True

def ensure_job_guard(doc, job_id, guard):
    jobs = doc.get('jobs') or {}
    if job_id not in jobs:
        return False
    job = jobs[job_id]
    if 'if' not in job or str(job['if']).strip() != guard.strip():
        job['if'] = guard
        return True
    return False

def _step_index(steps, name):
    for i, st in enumerate(steps):
        if isinstance(st, dict) and st.get('name') == name:
            return i
    return -1

def ensure_steps(doc, job_id, steps_spec):
    """
    steps_spec: list of { name: "...", run: "...", shell?: "...", uses?: "...", with?: {...} }
    - If step with same name exists: update fields (run/uses/with/shell).
    - Else: append new step at the end.
    """
    changed = False
    jobs = doc.get('jobs') or {}
    if job_id not in jobs:
        return False
    job = jobs[job_id]
    if 'steps' not in job or not isinstance(job['steps'], list):
        job['steps'] = []
    steps = job['steps']
    for spec in steps_spec:
        idx = _step_index(steps, spec.get('name'))
        if idx >= 0:
            # update existing step's keys (non-destructive)
            for k in ('run', 'uses', 'with', 'shell', 'env'):
                if k in spec:
                    if steps[idx].get(k) != spec[k]:
                        steps[idx][k] = spec[k]
                        changed = True
        else:
            steps.append(spec)
            changed = True
    return changed

def ensure_uses(doc, job_id, name, uses, with_dict=None):
    steps_spec = [{"name": name, "uses": uses, **({"with": with_dict} if with_dict else {})}]
    return ensure_steps(doc, job_id, steps_spec)

def hash_text(t):
    return hashlib.sha256(t.encode('utf-8')).hexdigest()[:12]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes")
    ap.add_argument("--dry-run", action="store_true", help="report only")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    manifest = load_manifest()
    targets = sorted([str(p) for p in WF_DIR.glob("*.y*ml")])
    patches = manifest.get("patches", [])

    results = []
    changed_files = 0

    for path in targets:
        rel = Path(path).relative_to(ROOT).as_posix()
        try:
            doc = yaml.load(Path(path).read_text(encoding="utf-8"))
        except Exception as e:
            results.append({"file": rel, "error": f"YAML parse error: {e}"})
            continue

        before = yaml.dump(doc, stream=None) or ""
        file_changes = []

        for p in patches:
            # match?
            pats = p.get("targets", [])
            if pats and not any(fnmatch.fnmatch(rel, pat) for pat in pats):
                continue

            op = p.get("op")
            if op == "ensure_on_triggers":
                snippet = load_snippet(p.get("snippet"))
                if snippet:
                    ensure_on_triggers(doc, snippet)
                    file_changes.append(op)
            elif op == "ensure_permissions":
                snippet = load_snippet(p.get("snippet"))
                if snippet:
                    ensure_permissions(doc, snippet)
                    file_changes.append(op)
            elif op == "ensure_concurrency":
                snippet = load_snippet(p.get("snippet"))
                if snippet:
                    ensure_concurrency(doc, snippet)
                    file_changes.append(op)
            elif op == "ensure_job_guard":
                if ensure_job_guard(doc, p["job_id"], p["guard"]):
                    file_changes.append(op)
            elif op == "ensure_steps":
                snippet = load_snippet(p.get("snippet"))
                if snippet:
                    # snippet format: { job_id: "<id>", steps: [ {name:..., run:...}, ... ] }
                    job_id = snippet.get("job_id")
                    steps_spec = snippet.get("steps", [])
                    if job_id and steps_spec:
                        if ensure_steps(doc, job_id, steps_spec):
                            file_changes.append(op)
            elif op == "ensure_uses":
                # direct definition in manifest
                if ensure_uses(doc, p["job_id"], p["name"], p["uses"], p.get("with")):
                    file_changes.append(op)
            else:
                # unknown op
                pass

        after = yaml.dump(doc, stream=None) or ""
        if after != before:
            changed_files += 1
            if apply:
                Path(path).write_text(after, encoding="utf-8")

        results.append({
            "file": rel,
            "changed": after != before,
            "ops_applied": file_changes,
            "before_hash": hash_text(before),
            "after_hash": hash_text(after)
        })

    summary = {
        "apply": apply,
        "files_seen": len(targets),
        "files_changed": changed_files,
        "patches_count": len(patches)
    }

    OUT_DIR.joinpath("AUTOPATCH_REPORT.json").write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")
    md = [
        "# AutoPatch Report",
        "",
        f"- Apply mode: **{apply}**",
        f"- Workflows scanned: **{len(targets)}**",
        f"- Files changed: **{changed_files}**",
        f"- Patches: **{len(patches)}**",
        "",
        "## Changes",
    ]
    for r in results:
        badge = "✅" if r.get("changed") else "—"
        md.append(f"- {badge} `{r['file']}` — ops: {', '.join(r['ops_applied']) or 'none'}")

    OUT_DIR.joinpath("AUTOPATCH_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
