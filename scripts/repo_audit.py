#!/usr/bin/env python3
"""
Repo Audit
- Inventories repo (size, sha256 sample) -> REPO_INVENTORY.{json,md}
- Compares against REPO_SPEC.json (if present) -> REPO_DIFF.json
- Flags forbidden globs, missing required files/dirs, extras
Safe, stdlib-only.
"""
import json, fnmatch, hashlib, time, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)

DEFAULT_IGNORE = [
    ".git/**","**/__pycache__/**","node_modules/**",".idea/**",".vscode/**",".DS_Store"
]

def load_spec():
    p = ROOT / "REPO_SPEC.json"
    base = {
        "ignore_globs": DEFAULT_IGNORE,
        "required_files": [],
        "required_dirs": [],
        "recommended_files": [],
        "forbidden_globs": ["**/*.env","**/secrets.*","**/*.pem","**/*.key","**/*.crt","private/**"]
    }
    if not p.exists():
        return base
    try:
        spec = json.loads(p.read_text(encoding="utf-8"))
        for k,v in base.items():
            spec.setdefault(k, v)
        return spec
    except Exception as e:
        base["_error"] = f"invalid REPO_SPEC.json: {e}"
        return base

def match_any(rel, globs):
    return any(fnmatch.fnmatch(rel, g) for g in globs)

def sha256_file(p: Path, cap=2_000_000):
    h = hashlib.sha256()
    n = 0
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk); n += len(chunk)
            if n >= cap: break
    return h.hexdigest(), n

def main():
    spec = load_spec()
    ignore = spec["ignore_globs"]

    files = []
    for p in ROOT.rglob("*"):
        if not p.is_file(): continue
        rel = p.relative_to(ROOT).as_posix()
        if match_any(rel, ignore): continue
        files.append(rel)
    files.sort()

    inv = []
    for rel in files:
        p = ROOT / rel
        try:
            digest, sampled = sha256_file(p)
            size = p.stat().st_size
        except Exception as e:
            digest, sampled, size = f"error:{e}", 0, 0
        inv.append({"path": rel, "size": size, "sha256": digest, "sampled_bytes": sampled})

    present = set(files)
    req_missing = [f for f in spec["required_files"] if f not in present]
    dir_missing = [d for d in spec["required_dirs"] if not (ROOT / d).exists()]
    rec_missing = [f for f in spec["recommended_files"] if f not in present]
    forb_hits = [rel for rel in files if match_any(rel, spec["forbidden_globs"])]
    wanted = set(spec["required_files"]) | set(spec["recommended_files"])
    extras = [rel for rel in files if rel not in wanted]

    inv_json = {
        "repo": os.getenv("GITHUB_REPOSITORY", ROOT.name),
        "generated_at": int(time.time()),
        "counts": {"files": len(files)},
        "inventory": inv
    }
    (OUT / "REPO_INVENTORY.json").write_text(json.dumps(inv_json, indent=2), encoding="utf-8")

    diff_json = {
        "summary": {
            "required_missing": len(req_missing),
            "dir_missing": len(dir_missing),
            "recommended_missing": len(rec_missing),
            "forbidden_hits": len(forb_hits),
            "extras": len(extras)
        },
        "required_missing": req_missing,
        "dir_missing": dir_missing,
        "recommended_missing": rec_missing,
        "forbidden_hits": forb_hits,
        "extras": extras,
        "spec_error": spec.get("_error")
    }
    (OUT / "REPO_DIFF.json").write_text(json.dumps(diff_json, indent=2), encoding="utf-8")

    # Markdown
    def sec(title, lst):
        md.append(f"## {title} ({len(lst)})")
        if not lst: md.append("- ✅ None"); return
        for i in lst[:300]: md.append(f"- `{i}`")

    md = [f"# Repo Inventory & Diff — {inv_json['repo']}",
          f"- Files scanned: **{len(files)}**",
          ""]
    sec("Required files missing", req_missing)
    sec("Required directories missing", dir_missing)
    sec("Recommended files missing", rec_missing)
    sec("Forbidden items present", forb_hits)
    sec("Extras (not required/recommended)", extras)
    if spec.get("_error"):
        md += ["", f"> Spec error: `{spec['_error']}`"]
    (OUT / "REPO_INVENTORY.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("OK repo_audit")

if __name__ == "__main__":
    main()
