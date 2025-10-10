#!/usr/bin/env python3
"""
Validate .github/autopatch/patches.yml

Checks:
- file exists and is valid YAML
- has top-level "version" (int) and "patches" (list)
- each patch has "id" (str) and "path" (str)
- each referenced patch file exists
- each patch file is valid YAML with top-level "version" or "actions"

Outputs a compact JSON report to stdout and writes a copy to /tmp/manifest-report.json.
Exits non-zero if any errors are found.
"""
from __future__ import annotations
import json, sys, pathlib

REPORT_PATH = pathlib.Path("/tmp/manifest-report.json")
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / ".github" / "autopatch" / "patches.yml"

def load_yaml(p: pathlib.Path):
    try:
        import yaml  # provided by setup-common-python composite action
    except Exception as e:
        return None, [f"PyYAML not available: {e!s}"]
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")), []
    except FileNotFoundError:
        return None, [f"Missing file: {p}"]
    except Exception as e:
        return None, [f"YAML parse error in {p}: {e!s}"]

def main() -> int:
    checks: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []

    # 1) Manifest presence + parse
    if not MANIFEST.exists():
        errors.append(f"Manifest not found: {MANIFEST}")
        report = {
            "ok": False, "checks": checks, "errors": errors, "warnings": warnings
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    data, parse_errs = load_yaml(MANIFEST)
    if parse_errs:
        errors.extend(parse_errs)
    else:
        checks.append({"status":"OK","msg":f"Loaded {MANIFEST.relative_to(REPO_ROOT)}"})

    # 2) Basic structure
    if not parse_errs:
        if not isinstance(data, dict):
            errors.append("Manifest root must be a mapping/dict.")
        else:
            # version
            if "version" not in data:
                errors.append('Missing top-level key: "version"')
            elif not isinstance(data["version"], int):
                errors.append('"version" must be an integer')

            # patches
            patches = data.get("patches")
            if patches is None:
                errors.append('Missing top-level key: "patches"')
                patches = []
            elif not isinstance(patches, list):
                errors.append('"patches" must be a list')
                patches = []

            # 3) Validate each entry
            for i, item in enumerate(patches, start=1):
                pre = f"patches[{i}]"
                if not isinstance(item, dict):
                    errors.append(f"{pre} must be a mapping/dict")
                    continue
                pid = item.get("id")
                ppath = item.get("path")
                if not pid or not isinstance(pid, str):
                    errors.append(f'{pre}.id missing or not a string')
                if not ppath or not isinstance(ppath, str):
                    errors.append(f'{pre}.path missing or not a string')
                    continue

                patch_file = REPO_ROOT / ppath
                if not patch_file.exists():
                    errors.append(f'{pre}.path not found: {ppath}')
                    continue

                pdata, perrs = load_yaml(patch_file)
                if perrs:
                    errors.extend([f"{pre}: {x}" for x in perrs])
                else:
                    # sanity check on patch shape
                    if not isinstance(pdata, dict):
                        errors.append(f"{pre}: patch must parse to a mapping/dict")
                    elif "version" not in pdata and "actions" not in pdata:
                        warnings.append(f"{pre}: patch has no 'version' or 'actions' key (unusual)")

    ok = len(errors) == 0
    summary = f"✔ OK: {len(checks)} | ⚠ {len(warnings)} | ✖ {len(errors)}"
    report = {
        "ok": ok,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "summary": summary
    }

    try:
        REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception:
        pass

    print(json.dumps(report, indent=2))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
