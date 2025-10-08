#!/usr/bin/env python3
"""
Collect Self-Healing Manifest
- Lists workflows, scripts, API, UI, infra, config in SELF_HEALING_MANIFEST.{json,md}
- Creates empty REMEDIATIONS.md and GAPS.json if missing
"""
import json, datetime, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "self_healing_out"
OUT.mkdir(parents=True, exist_ok=True)

def ls(globs):
    out=[]
    for g in globs:
        out += [str(p) for p in ROOT.glob(g) if p.is_file()]
    return sorted(out)

def main():
    manifest = {
        "repo": os.getenv("GITHUB_REPOSITORY", ROOT.name),
        "branch": os.getenv("GITHUB_REF_NAME", ""),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "measures": {
            "workflows": ls([".github/workflows/*.yml",".github/workflows/*.yaml"]),
            "scripts": ls(["scripts/*.py","scripts/*.sh"]),
            "config": ls(["render.yaml","api/requirements.txt","package.json","pyproject.toml"]),
            "api": ls(["api/main.py","api/app/main.py"]),
            "ui": ls(["public/diag.html","public/quicktriggers.html"]),
            "docs": ls(["README.md","docs/*.md"])
        }
    }
    (OUT/"SELF_HEALING_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT/"SELF_HEALING_MANIFEST.md").write_text(
        "# Self-Healing Manifest\n\n```\n"+json.dumps(manifest, indent=2)+"\n```\n", encoding="utf-8")

    (OUT/"GAPS.json").write_text(json.dumps({"note":"populate during reviews"}, indent=2), encoding="utf-8") \
        if not (OUT/"GAPS.json").exists() else None
    (OUT/"REMEDIATIONS.md").write_text("# Remediations Log\n", encoding="utf-8") \
        if not (OUT/"REMEDIATIONS.md").exists() else None

    print("OK collect_self_healing")

if __name__ == "__main__":
    main()
