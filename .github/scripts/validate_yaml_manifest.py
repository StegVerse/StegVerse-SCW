#!/usr/bin/env python3
"""
scripts/validate_yaml_manifest.py

Validates .github/autopatch/patches.yml (or MANIFEST env) before running AutoPatch.
- Produces friendly JSON output PLUS GitHub::error annotations.
- Checks: file exists, YAML parses, no tab characters, correct schema, duplicate ids, missing paths.
- Exits 1 on failure; 0 on success.
"""

import os, sys, json, pathlib
from typing import Any, Dict, List

MANIFEST = os.environ.get("MANIFEST", ".github/autopatch/patches.yml")

def echo_error(msg: str) -> None:
    # Also emit a GitHub annotation so the error is highlighted in Actions logs.
    print(f"::error title=Manifest validation failed::{msg}")
    sys.stderr.write(msg + "\n")

def load_yaml(path: str):
    try:
        import yaml  # PyYAML
    except Exception:
        echo_error("PyYAML is not installed. Add `pip install pyyaml` before running this script.")
        return None, [{"msg": "Missing dependency: PyYAML"}], []

    p = pathlib.Path(path)
    if not p.exists():
        return None, [{"msg": f"Manifest not found: {path}"}], []

    text = p.read_text(encoding="utf-8", errors="replace")

    if "\t" in text:
        return None, [{"msg": "Manifest contains TAB characters. Use spaces only."}], []

    try:
        data = yaml.safe_load(text)
    except Exception as e:
        return None, [{"msg": f"YAML parse error: {e}"}], []

    return data, [], []

def validate_schema(doc: Any) -> Dict[str, List[Dict[str, str]]]:
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    if not isinstance(doc, dict):
        errors.append({"msg": "Root must be a mapping (dict). Example:\n  version: 1\n  patches: []"})
        return {"errors": errors, "warnings": warnings}

    version = doc.get("version")
    if version not in (1, "1"):
        errors.append({"msg": "Field 'version' must be 1."})

    patches = doc.get("patches")
    if patches is None:
        errors.append({"msg": "Field 'patches' is required (list)."})
        return {"errors": errors, "warnings": warnings}

    if not isinstance(patches, list):
        errors.append({"msg": "Field 'patches' must be a list."})
        return {"errors": errors, "warnings": warnings}

    seen_ids = set()
    for idx, item in enumerate(patches, 1):
        if not isinstance(item, dict):
            errors.append({"msg": f"patches[{idx}] must be a mapping with 'id' and 'path'."})
            continue

        pid = item.get("id")
        pth = item.get("path")

        if not pid or not isinstance(pid, str):
            errors.append({"msg": f"patches[{idx}].id is required and must be a string."})
        else:
            if pid in seen_ids:
                errors.append({"msg": f"Duplicate patch id: {pid}"})
            seen_ids.add(pid)

        if not pth or not isinstance(pth, str):
            errors.append({"msg": f"patches[{idx}].path is required and must be a string."})
        else:
            # Warn (not error) if path missing — may be committed in same push/run.
            if not pathlib.Path(pth).exists():
                warnings.append({"msg": f"Patch path not found (may be added later): {pth}"})

    return {"errors": errors, "warnings": warnings}

def main() -> None:
    doc, load_errs, load_warns = load_yaml(MANIFEST)

    if load_errs:
        out = {"ok": False, "errors": load_errs, "warnings": load_warns}
        print(json.dumps(out, indent=2))
        for e in load_errs:
            echo_error(e.get("msg", "Unknown manifest load error"))
        sys.exit(1)

    res = validate_schema(doc)
    ok = len(res["errors"]) == 0
    out = {"ok": ok, **res}
    print(json.dumps(out, indent=2))

    if not ok:
        for e in res["errors"]:
            echo_error(e.get("msg", "Schema error"))
        sys.exit(1)

if __name__ == "__main__":
    main()
