#!/usr/bin/env python3
"""
Topic Drift Auditor
- Scans repo for:
  * files with @idea:TAG or @attic markers
  * unused/isolated files by simple heuristics
- Parses recent git commits for [topic:<tag>] markers
- Produces self_healing_out/DRIFT_REPORT.{json,md}

Heuristics are intentionally simple & safe (no deletions).
"""
import os, re, json, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "self_healing_out"; OUT.mkdir(parents=True, exist_ok=True)

IDEA_RE = re.compile(r'@idea:([a-zA-Z0-9_\-]+)')
ATTIC_RE = re.compile(r'@attic\b')
TOPIC_RE = re.compile(r'\[topic:([a-zA-Z0-9_\-]+)\]')

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".idea", ".vscode"}
CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yml", ".yaml", ".md", ".html", ".sh"}

def list_files():
    files = []
    for p in ROOT.rglob("*"):
        if not p.is_file(): continue
        rel = p.relative_to(ROOT).as_posix()
        parts = rel.split("/")
        if any(seg in IGNORE_DIRS for seg in parts): continue
        files.append(rel)
    return files

def scan_markers(files):
    ideas, attic = {}, []
    for rel in files:
        if not any(rel.endswith(ext) for ext in CODE_EXTS): continue
        try:
            text = (ROOT/rel).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in IDEA_RE.findall(text):
            ideas.setdefault(m, []).append(rel)
        if ATTIC_RE.search(text) or rel.startswith("ATTIC/"):
            attic.append(rel)
    return ideas, attic

def git(cmd):
    return subprocess.check_output(["git"]+cmd, cwd=str(ROOT)).decode().strip()

def recent_commits(n=200):
    try:
        log = git(["log", f"-n{n}", "--pretty=%H%x09%ad%x09%s", "--date=short"])
    except Exception:
        return []
    out = []
    for line in log.splitlines():
        try:
            sha, date, subj = line.split("\t", 2)
        except ValueError:
            continue
        tags = TOPIC_RE.findall(subj)
        out.append({"sha":sha, "date":date, "subject":subj, "topics":tags})
    return out

def simple_unused_heuristics(files):
    """
    Gentle heuristic:
    - mark files under scripts/, docs/, ATTIC/ as not unused
    - mark isolated .py files not imported by others as 'possibly_unused'
      (best-effort by keyword search; safe for guidance only)
    """
    python_files = [f for f in files if f.endswith(".py")]
    imports = {f: set() for f in python_files}

    # Build a reverse import map by searching 'import X' / 'from X import'
    module_names = {f[:-3].replace("/", "."): f for f in python_files if not f.endswith("__init__.py")}
    for f in python_files:
        try:
            text = (ROOT/f).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for mod in module_names:
            # crude search; avoid self-match
            if module_names[mod] == f: continue
            if f"import {mod}" in text or f"from {mod} import" in text:
                imports[module_names[mod]].add(f)

    possibly_unused = []
    for mod, srcs in imports.items():
        rel = module_names[mod]
        if rel.startswith(("scripts/","docs/","ATTIC/")):
            continue
        if len(srcs) == 0:
            possibly_unused.append(rel)

    return sorted(possibly_unused)

def main():
    files = list_files()
    ideas, attic = scan_markers(files)
    commits = recent_commits()
    unused = simple_unused_heuristics(files)

    # Drift metric: % commits without a [topic:...] tag in last 200
    no_topic = sum(1 for c in commits if not c["topics"])
    drift_ratio = (no_topic / max(1, len(commits))) if commits else None

    report = {
        "generated_at": int(time.time()),
        "files_scanned": len(files),
        "idea_tags": {k: sorted(v) for k,v in ideas.items()},
        "attic_files": sorted(attic),
        "possibly_unused": unused,
        "commit_topics_last200": commits,
        "drift_ratio_no_topic": drift_ratio,
        "guidance": {
            "topic_tag_hint": "Add [topic:<tag>] in commit subjects to link work to themes.",
            "attic_hint": "Move paused code to ATTIC/ with @attic header instead of deleting.",
            "ideas_hint": "Cross-reference @idea:<tag> with docs/IDEAS.md entries."
        }
    }
    (OUT/"DRIFT_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Human-readable MD
    md = []
    md.append("# Drift Report\n")
    md.append(f"- Files scanned: **{len(files)}**")
    if drift_ratio is not None:
        md.append(f"- Commits without topic tag: **{int(drift_ratio*100)}%** (last 200)")
    md.append("\n## Idea tags found")
    if ideas:
        for tag, paths in sorted(report["idea_tags"].items()):
            md.append(f"- **{tag}** ({len(paths)})")
            for p in paths[:20]:
                md.append(f"  - `{p}`")
    else:
        md.append("- None")

    md.append("\n## Files in ATTIC/ or marked @attic")
    if report["attic_files"]:
        for p in report["attic_files"][:50]:
            md.append(f"- `{p}`")
    else:
        md.append("- None")

    md.append("\n## Possibly unused Python modules (heuristic)")
    if unused:
        for p in unused[:50]:
            md.append(f"- `{p}`")
        md.append("\n> Heuristic: verify before archiving to ATTIC/. Not authoritative.")
    else:
        md.append("- None")

    md.append("\n## Recent commit topics (last 20)")
    for c in commits[:20]:
        md.append(f"- {c['date']} {c['sha'][:7]} — {c['subject']}  (topics: {', '.join(c['topics']) or '—'})")

    (OUT/"DRIFT_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print("OK drift_report")

if __name__ == "__main__":
    main()
