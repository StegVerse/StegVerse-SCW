#!/usr/bin/env python3
"""
Compatibility shim: delegate to yaml_corrector.py so either name works.
"""
import runpy, sys, pathlib

me = pathlib.Path(__file__).resolve()
legacy = me.with_name("yaml_corrector.py")
if not legacy.exists():
    print("ERROR: scripts/yaml_corrector.py not found for v2 shim", file=sys.stderr)
    sys.exit(1)

# Preserve --apply if present
sys.argv = ["yaml_corrector.py"] + [a for a in sys.argv[1:] if a == "--apply"]
runpy.run_path(str(legacy), run_name="__main__")
