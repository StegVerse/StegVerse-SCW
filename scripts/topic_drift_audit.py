#!/usr/bin/env python3
"""
Topic Drift Audit
- Scans files for @idea:<tag>, @attic markers
- Lists possibly-unused Python modules (simple import heuristic)
- Samples last 200 commit subjects for [topic:<tag>] markers
Writes DRIFT_REPORT.{json,md}
"""
import re, json, subprocess, time, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)

IDEA_RE = re.compile(r'@idea:([a-zA-Z0-9_\-]+)')
TOPIC_RE = re.compile(r'\[topic:([a-zA-Z0-9_\-]+)\]')
ATTIC_RE = re.compile(r'@attic\b')
IGNORE_DIRS = {".git","node_modules","__pycache__", ".idea", ".vscode"}
SCAN_EXTS = {".py",".ts",".tsx",".js",".jsx",".json",".yml",".yaml",".md",".html",".sh"}

def files():
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file(): continue
        rel = p.relative_to(ROOT).as_posix()
        parts = rel.split("/")
        if any(seg in IGNORE_DIRS for seg in parts): continue
        out.append(rel)
    return out

def scan_markers(paths):
    ideas, attic = {}, []
    for rel in paths:
        if not any(rel.endswith(e) for e in SCAN_EXTS): continue
        try:
            txt = (ROOT/rel).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for tag in IDEA_RE.findall(txt):
            ideas.setdefault(tag, []).append(rel)
        if rel.startswith("ATTIC/") or ATTIC_RE.search(txt):
            attic.append(rel)
    return {k: sorted(v) for k,v in ideas.items()}, sorted(attic)

def git(cmd):
    return subprocess.check_output(["git"] + cmd, cwd=str(ROOT)).decode().strip()

def recent_commits(n=200):
    try:
        log = git(["log", f"-n{n}", "--pretty=%H%x09%ad%x09%s", "--date=short"])
    except Exception:
        return []
    out = []
    for line in log.splitlines():
        try: sha, date, subj = line.split("\t", 2)
        except: continue
        out.append({"sha":sha, "date":date, "subject":subj, "topics":TOPIC_RE.findall(subj)})
    return out

def simple_unused(paths):
    py = [f for f in paths if f.endswith(".py")]
    mods = {f[:-3].replace("/","."): f for f in py if not f.endswith("__init__.py")}
    reverse = {m:set() for m in mods}
    for f in py:
        try: t = (ROOT/f).read_text(encoding="utf-8", errors="ignore")
        except: continue
        for m in mods:
            if mods[m] == f: continue
            if f"import {m}" in t or f"from {m} import" in t:
                reverse[m].add(f)
    unused = []
    for m, srcs in reverse.items():
        rel = mods[m]
        if rel.startswith(("scripts/","docs/","ATTIC/")): continue
        if len(srcs)==0:
            unused.append(rel)
    return sorted(unused)

def main():
    paths = files()
    ideas, attic = scan_markers(paths)
    commits = recent_commits()
    unused = simple_unused(paths)
    drift_ratio = None
    if commits:
        no_topic = sum(1 for c in commits if not c["topics"])
        drift_ratio = no_topic / max(1,len(commits))

    rep = {
        "generated_at": int(time.time()),
        "files_scanned": len(paths),
        "idea_tags": ideas,
        "attic_files": attic,
        "possibly_unused": unused,
        "commit_topics_last200": commits,
        "drift_ratio_no_topic": drift_ratio
    }
    (OUT/"DRIFT_REPORT.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")

    md = [
        "# Drift Report",
        f"- Files scanned: **{len(paths)}**",
        f"- Commits without topic tag: **{int(drift_ratio*100)}%** (last 200)" if drift_ratio is not None else "- Commits without topic tag: —",
        "",
        "## Idea tags found"
    ]
    if ideas:
        for tag, lst in sorted(ideas.items()):
            md.append(f"- **{tag}** ({len(lst)})")
            for p in lst[:30]:
                md.append(f"  - `{p}`")
    else:
        md.append("- None")

    md += ["", "## Files in ATTIC/ or marked @attic"]
    md += ([f"- `{p}`" for p in attic[:50]] or ["- None"])

    md += ["", "## Possibly unused Python modules (heuristic)"]
    md += ([f"- `{p}`" for p in unused[:50]] or ["- None"])

    md += ["", "## Recent commit topics (last 20)"]
    md += [f"- {c['date']} {c['sha'][:7]} — {c['subject']}  (topics: {', '.join(c['topics']) or '—'})" for c in commits[:20]]

    (OUT/"DRIFT_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("OK drift_report")

if __name__ == "__main__":
    main()
