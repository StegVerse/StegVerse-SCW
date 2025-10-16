# StegVerse-SCW
[![Workflows](.github/badges/workflows.svg)](https://github.com/StegVerse/StegVerse-SCW/actions/workflows/workflows-badges.yml)

<!-- workflows:status -->
...
<!-- /workflows:status -->

Self-healing CI + runtime harness for StegTalk and related services.

## Quick Start (mobile-friendly)

- Trigger checks by **adding a file**:
  - `echo go > .github/trigger/supercheck/run-1.txt` (runs One-Button Supercheck)
  - `echo go > .github/trigger/preflight/run-1.txt` (runs Workflow Preflight)
  - `echo go > .github/trigger/autopatch/run-1.txt` (runs Auto Patch)

- Or run from **Actions → Run workflow**.

> **Note:** Some self-healing and dispatch workflows (like YAML Bulk Autofix, AutoDocs Verify, and AutoPatch Apply)
> now require a **Personal Access Token (PAT)** or **GitHub App token** with `workflow` and `contents` write scopes.
> Add it under **Settings → Secrets and variables → Actions → New repository secret**
> with the name `PAT_WORKFLOW`.  
> The system will automatically detect and use it if available.

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

## Maintenance & Self-Repair

StegVerse-SCW includes first-aid and self-repair workflows:

| Workflow | Purpose | Notes |
|-----------|----------|-------|
| **fix-dispatch-triggers.yml** | Scans and normalizes `workflow_dispatch` blocks. | Run after adding new workflows. |
| **yaml-bulk-autofix.yml** | Automatically repairs parse errors and indentation issues. | Requires `PAT_WORKFLOW` for commit access. |
| **workflows-first-aid.yml** | Ensures all Actions remain runnable after upstream GitHub changes. | Runs nightly. |
| **actions-permission-check.yml** | Verifies token scopes and repo permissions. | Should show `403` only if `PAT_WORKFLOW` is missing. |

**Tip:** If a self-healing workflow fails with  
`Resource not accessible by integration` or `Workflow does not have 'workflow_dispatch' trigger`,  
add a token with the `workflow` scope and rerun `fix-dispatch-triggers.yml`.

## Contributing

- Use topic tags in commit messages: `[topic:supercheck]`, `[topic:scaffolding]`, etc.
- Ideas/experiments can be tagged with `@idea:<slug>` inside files; extras are parked in `ATTIC/`.
