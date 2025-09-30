# Trigger Files Guide

This folder contains **file-based triggers** for GitHub Actions workflows.  
Each subfolder corresponds to a workflow that can be run simply by committing a file.

---

## Available Triggers

- **Preflight**
  - Path: `.github/trigger/preflight/`
  - Drop a file like `run-1.txt` with content `go` (or any text).
  - On commit to `main`, the `Workflow Preflight` job runs.
  - Useful for validating & auto-fixing workflows.

- **Supercheck**
  - Path: `.github/trigger/supercheck/`
  - Drop a file like `run-1.txt`.
  - Runs the **One-Button Supercheck** (YAML corrector, diagnostics, repo audit, drift, triage).
  - Produces a bundle artifact with full reports.

- **Rebuild**
  - Path: `.github/trigger/rebuild/`
  - Drop a file like `run-1.txt`.
  - Runs the **Rebuild Kit** workflow to package workflows, scripts, docs, and manifests into a portable bundle.
  - Always includes a breadcrumb log of what triggered it.

---

## Usage Pattern

1. Create a file in the appropriate trigger folder:
   ```bash
   echo "go" > .github/trigger/supercheck/run-1.txt
   git add .github/trigger/supercheck/run-1.txt
   git commit -m "Trigger supercheck"
   git push
