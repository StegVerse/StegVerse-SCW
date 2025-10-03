# StegVerse-SCW

Self-healing CI + runtime harness for StegTalk and related services.

## Quick Start (mobile-friendly)

- Trigger checks by **adding a file**:
  - `echo go > .github/trigger/supercheck/run-1.txt` (runs One-Button Supercheck)
  - `echo go > .github/trigger/preflight/run-1.txt` (runs Workflow Preflight)
  - `echo go > .github/trigger/autopatch/run-1.txt` (runs Auto Patch)

- Or run from **Actions → Run workflow**.

## Workflows

- **One-Button Supercheck**: YAML corrector → known-issue auto-fix → runtime diagnostics → repo audit → drift → auto-triage → bundles.
- **Universal Fix-It**: precision + sweep fixers for YAML and common CI nits; generates sweep bundle.
- **Preflight**: validates workflows and normalizes them before big changes.
- **Rebuild Kit**: produces a zero-secret archive of all critical files for disaster recovery.
- **Nightly Snapshot**: rolls up state for time-series tracking.
- **Auto Patch**: applies `patches/manifest.json` across workflows; logs changes.

See `docs/WORKFLOWS.md` for details.

## Self-Healing / Autonomy

- **YAML Corrector** & **Auto-Fix** repair common syntax/structure errors automatically.
- **Auto-Triage** moves extras to `ATTIC/`, scaffolds missing files, removes forbidden files.
- **Telemetry** & **last-two summaries** capture outcomes for quick status on mobile.

## Disaster Recovery

- Download the latest **Rebuild Kit** from Actions → Artifacts → `rebuild_kit_bundle`.
- Unpack on a fresh environment to restore workflows/scripts/docs quickly.

## Contributing

- Use topic tags in commit messages: `[topic:supercheck]`, `[topic:scaffolding]`, etc.
- Ideas/experiments can be tagged with `@idea:<slug>` inside files; extras are parked in `ATTIC/`.
