# scripts/validate_yaml_manifest.py
# Validate .github/autopatch/patches.yml and print a friendly report.
# Exits 1 on problems so the workflow fails early (no ugly tracebacks).

import os, sys, json, re
from typing import List, Dict

try:
    import yaml  # PyYAML
except Exception:
    print("::error title=Missing dependency::PyYAML is not installed. Run: pip install pyyaml")
    sys.exit(1)

MANIFEST = os.environ.get("MANIFEST", ".github/autopatch/patches.yml")

def load_yaml(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if "\t" in text:
            return None, [{"msg": "Manifest contains tab characters (use spaces only)."}], []
        data = yaml.safe_load(text) or {}
        return data, [], []
    except FileNotFoundError:
        return None, [{"msg": f"Manifest not found: {path}"}], []
    except yaml.YAMLError as e:
        return None, [{"msg": f"YAML parse error in {path}: {e}"}], []
    except Exception as e:
        return None, [{"msg": f"Unexpected error reading {path}: {e}"}], []

def validate_schema(doc: Dict) -> Dict[str, List[Dict[str, str]]]:
    errors, warnings = [], []

    if not isinstance(doc, dict):
        return {"errors": [{"msg": "Manifest root must be a mapping (dict)."}], "warnings": warnings}

    version = doc.get("version")
    patches = doc.get("patches")

    if version not in (1, "1"):
        errors.append({"msg": "Field 'version' must be 1."})

    if patches is None:
        errors.append({"msg": "Field 'patches' is required (list)."})
        return {"errors": errors, "warnings": warnings}

    if not isinstance(patches, list):
        errors.append({"msg": "Field 'patches' must be a list."})
        return {"errors": errors, "warnings": warnings}

    seen_ids = set()
    for i, it in enumerate(patches, 1):
        if not isinstance(it, dict):
            errors.append({"msg": f"patches[{i}] must be a mapping with 'id' and 'path'."})
            continue
        pid = it.get("id")
        pth = it.get("path")
        if not pid or not isinstance(pid, str):
            errors.append({"msg": f"patches[{i}].id is required and must be a string."})
        else:
            if pid in seen_ids:
                errors.append({"msg": f"Duplicate patch id: {pid}"})
            seen_ids.add(pid)
        if not pth or not isinstance(pth, str):
            errors.append({"msg": f"patches[{i}].path is required and must be a string."})
        else:
            if not os.path.exists(pth):
                warnings.append({"msg": f"Patch path not found (may be added later): {pth}"})

    return {"errors": errors, "warnings": warnings}

def main():
    doc, load_errs, load_warns = load_yaml(MANIFEST)
    if load_errs:
        out = {"ok": False, "errors": load_errs, "warnings": load_warns}
        print(json.dumps(out, indent=2))
        sys.exit(1)

    res = validate_schema(doc)
    ok = len(res["errors"]) == 0
    out = {"ok": ok, **res}
    print(json.dumps(out, indent=2))
    if not ok:
        sys.exit(1)

if __name__ == "__main__":
    main()
