# .github/workflows/ — GitHub Actions Workflows

This folder contains the **automation harness** for StegVerse-SCW.  
Most workflows can be triggered either manually from the Actions tab or
by committing a file to a trigger folder.

## Major Workflows

- `supercheck.yml` — **One-Button Supercheck**: YAML correction, autofix, diagnostics, repo audit, drift, triage, reports.
- `universal_fixit.yml` — **Universal Fix-It**: precision + sweep corrections for workflows.
- `preflight.yml` — lightweight validator to catch broken workflows before merge.
- `rebuild_kit.yml` — produces a disaster-recovery archive of critical files.
- `nightly_snapshot.yml` — time-series state snapshot.
- `auto_patch.yml` — applies `patches/manifest.json` rules across workflows.

## Triggers

- `push` filters: commit a file into `.github/trigger/<workflow>/` to run on mobile easily.
- `workflow_dispatch`: all workflows are manually runnable with optional inputs.

## Reusables

- `_reusables/ensure-tools.yml` — installs apt/pip tools consistently.
- `_reusables/upload-sweep.yml` — standard artifact uploader.
- `_reusables/telemetry.yml` — job telemetry, always-on.
