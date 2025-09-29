#!/usr/bin/env python3
import os, sys, json, hashlib, fnmatch, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)

DEFAULT_IGNORE = [".git/**", "**/__pycache__/**", "node_modules/**", ".idea/**", ".vscode/**", ".DS_Store"]

def sha256_file(p: Path, max_bytes=2_000_000):
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            n=0
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk); n+=len(chunk)
                if n>=max_bytes: break
        return h.hexdigest(), n
    except Exception as e:
        return f"error:{e}", 0

def load_spec():
    spec_file = ROOT / "REPO_SPEC.json"
    if spec_file.exists():
        try:
            return json.loads(spec_file.read_text(encoding="utf-8"))
        except Exception as e:
            return {"_error": f"failed to parse REPO_SPEC.json: {e}"}
    # no spec => create a minimal default that expects nothing and forbids secrets
    return {
        "$schema":"https://stegverse/specs/repo-spec-v1",
        "ignore_globs": DEFAULT_IGNORE,
        "required_files": [],
        "required_dirs": [],
        "recommended_files": [],
        "forbidden_globs": ["**/*.env","**/secrets.*","**/*.pem","**/*.key","**/*.crt","private/**"]
    }

def is_ignored(rel: str, ignore_globs):
    for pat in ignore_globs:
        if fnmatch.fnmatch(rel, pat):
            return True
    return False

def all_files(ignore_globs):
    files = []
    for p in ROOT.rglob("*"):
        if not p.is_file(): continue
        rel = p.relative_to(ROOT).as_posix()
        if is_ignored(rel, ignore_globs): continue
        files.append(rel)
    return sorted(files)

def match_any(rel, patterns):
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat) or rel == pat:
            return True
    return False

def main():
    spec = load_spec()
    ignore = spec.get("ignore_globs") or DEFAULT_IGNORE
    required_files = spec.get("required_files", [])
    required_dirs  = spec.get("required_dirs", [])
    recommended    = spec.get("recommended_files", [])
    forbidden      = spec.get("forbidden_globs", [])

    files = all_files(ignore)
    inventory = []
    for rel in files:
        p = ROOT / rel
        size = p.stat().st_size
        digest, read = sha256_file(p)
        inventory.append({"path": rel, "size": size, "sha256": digest, "sampled_bytes": read})

    # compute missing/extra/forbidden
    present_set = set(files)
    required_missing = [f for f in required_files if f not in present_set]
    dir_missing = [d for d in required_dirs if not (ROOT / d).exists()]
    recommended_missing = [f for f in recommended if f not in present_set]

    forbidden_hits = []
    for rel in files:
        if match_any(rel, forbidden):
            forbidden_hits.append(rel)

    # "extra" = files that are neither required nor recommended and not ignored by spec
    wanted = set(required_files) | set(recommended)
    extras = [rel for rel in files if rel not in wanted]

    ts = int(time.time())
    inv_json = {
        "repo": os.getenv("GITHUB_REPOSITORY", ROOT.name),
        "generated_at": ts,
        "spec_loaded": "REPO_SPEC.json exists" if (ROOT/"REPO_SPEC.json").exists() else "default",
        "counts": {"files": len(files)},
        "inventory": inventory
    }
    diff_json = {
        "summary": {
            "required_missing": len(required_missing),
            "dir_missing": len(dir_missing),
            "recommended_missing": len(recommended_missing),
            "forbidden_hits": len(forbidden_hits),
            "extras": len(extras)
        },
        "required_missing": required_missing,
        "dir_missing": dir_missing,
        "recommended_missing": recommended_missing,
        "forbidden_hits": forbidden_hits,
        "extras": extras
    }

    (OUT/"REPO_INVENTORY.json").write_text(json.dumps(inv_json, indent=2), encoding="utf-8")
    (OUT/"REPO_DIFF.json").write_text(json.dumps(diff_json, indent=2), encoding="utf-8")

    # human-readable
    md = []
    md.append(f"# Repo Inventory & Diff — {os.getenv('GITHUB_REPOSITORY', ROOT.name)}")
    md.append("")
    md.append(f"- Generated: <t:{ts}:F>")
    md.append(f"- Files scanned: **{len(files)}**")
    md.append(f"- Spec: **{'REPO_SPEC.json' if (ROOT/'REPO_SPEC.json').exists() else 'default'}**")
    md.append("")
    def section(title, items, limit=None):
        md.append(f"## {title} ({len(items)})")
        if not items:
            md.append("- ✅ None")
            md.append("")
            return
        if limit: items = items[:limit]
        for it in items:
            md.append(f"- `{it}`")
        md.append("")
    section("Required files missing", required_missing)
    section("Required directories missing", dir_missing)
    section("Recommended files missing", recommended_missing[:100], limit=None)
    section("Forbidden items present", forbidden_hits[:100], limit=None)
    section("Extras (not required/recommended)", extras[:200], limit=None)
    (OUT/"REPO_INVENTORY.md").write_text("\n".join(md), encoding="utf-8")

    print("OK: wrote self_healing_out/REPO_INVENTORY.md and REPO_DIFF.json")

if __name__ == "__main__":
    main()
