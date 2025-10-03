# scripts/ — Utility + Self-Healing Scripts

This folder holds the **brains of the self-healing system**.  
Each script is designed to run standalone from CI (or locally) and produces
machine-readable and human-readable reports.

## Core Scripts

- `yaml_corrector_v2.py` — modern YAML validator/corrector. Normalizes structure, fixes indentation, inserts missing keys.
- `yaml_corrector.py` — legacy fallback version.
- `auto_fix_known_issues.py` — small rule engine for common workflow nits (YAML-001, etc).
- `repo_audit.py` — inventory of repo files, flags missing vs. extra, writes `REPO_INVENTORY.md`.
- `topic_drift_audit.py` — checks for files/topics drifting from declared purpose, writes `DRIFT_REPORT.md`.
- `collect_self_healing.py` — collects signals into `SELF_HEALING_MANIFEST.md`.
- `auto_triage.py` — scaffolds missing dirs, moves strays into `ATTIC/`, removes forbidden files.
- `validate_and_fix.py` — legacy precision fixer.
- `sweep_all_workflows.py` — legacy sweep across all workflows.

## Patch Runner

- `auto_patch.py` — reads `patches/manifest.json` and applies regex/anchor-based patch rules across workflows.

## Conventions

- All scripts write JSON + MD reports into `self_healing_out/`.
- All should exit 0 unless a **fatal error** occurs; non-critical failures are captured in reports.
- Designed to be run from workflows or local CLI (`python3 scripts/foo.py --apply`).
