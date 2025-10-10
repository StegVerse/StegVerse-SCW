#!/usr/bin/env python3
import sys, os, json, re, yaml, pathlib
from yaml.parser import ParserError
from yaml.scanner import ScannerError

MANIFEST = pathlib.Path(".github/autopatch/patches.yml")

def log(msg): print(msg, flush=True)

def safe_load_yaml(path: pathlib.Path):
    text = path.read_text(encoding="utf-8")
    # Auto-repair common YAML issues
    fixed = re.sub(r"^\?", "-", text, flags=re.M)
    fixed = fixed.replace("\t", "  ")
    if fixed != text:
        log(f"🧩 Auto-fixed formatting in {path}")
        path.write_text(fixed, encoding="utf-8")

    try:
        return yaml.safe_load(fixed)
    except (ParserError, ScannerError) as e:
        log(f"::error title=YAML parse error::{e}")
        sys.exit(2)

def validate_schema(data):
    ok, errors, warnings = True, [], []

    if not isinstance(data, dict) or "patches" not in data:
        errors.append("Manifest root must contain 'patches' list.")
        return False, errors, warnings

    seen = set()
    for i, p in enumerate(data["patches"], start=1):
        prefix = f"patch[{i}]"
        if not isinstance(p, dict):
            errors.append(f"{prefix}: must be a mapping (id/path/enabled).")
            ok = False
            continue
        pid = p.get("id")
        path = p.get("path")
        if not pid:
            errors.append(f"{prefix}: missing 'id'")
        elif pid in seen:
            errors.append(f"{prefix}: duplicate id '{pid}'")
        else:
            seen.add(pid)
        if not path:
            errors.append(f"{prefix}: missing 'path'")
        elif not pathlib.Path(path).exists():
            warnings.append(f"{prefix}: file not found → {path}")
        if "enabled" not in p:
            warnings.append(f"{prefix}: missing 'enabled' (defaulting True)")

    return ok and not errors, errors, warnings

def main():
    log("🧩 Running manifest validator…")

    if not MANIFEST.exists():
        log("::error title=Manifest missing::.github/autopatch/patches.yml not found")
        sys.exit(2)

    data = safe_load_yaml(MANIFEST)
    ok, errors, warnings = validate_schema(data)

    summary = {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "summary": f"✅ OK: {0 if not ok else len(data.get('patches',[]))} | ⚠️ {len(warnings)} | ❌ {len(errors)}"
    }

    print(json.dumps(summary, indent=2))

    if errors:
        sys.exit(2)
    elif warnings:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
