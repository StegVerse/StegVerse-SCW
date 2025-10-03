# CI Workflows Overview

## One-Button Supercheck
Runs, in order:
1. YAML Corrector (v2 preferred; legacy fallback)
2. Auto-fix known issues (e.g., YAML-001)
3. Validate with `actionlint` and `yamllint`
4. Runtime diagnostics (API + Worker)
5. Repo audit and topic drift
6. Self-healing scan
7. Auto-triage (optionally apply changes)
8. Commit/PR (optional)
9. Assemble report and upload bundles
10. Telemetry

### Trigger
- Manual dispatch input fields, or
- Commit a file to `.github/trigger/supercheck/`.

## Universal Fix-It
- Precision correction (line-level)
- Sweep across all workflows
- Always emits a bundle (or a placeholder)

## Preflight
- Minimal validator; normalizes YAML and avoids broken workflows landing in `main`.

## Rebuild Kit
- Packages critical folders into `out/rebuild_kit_*.zip` with a small manifest.

## Nightly Snapshot
- Time-series state rollup for drift/health.

## Auto Patch
- Applies `patches/manifest.json` to unify common steps across repos/workflows.
