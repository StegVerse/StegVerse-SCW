# 🧭 TaskOps Index

Central index for TaskOps-managed flows in this repo.

## First-Run / Bring-up
- **Checklist**: `CHECKLIST-HCB-FIRST-RUN.md` — auto-updated by CI
- **Watcher/Updater**: `.github/workflows/taskops-first-run-update.yml`
- **Completion Gate**: `.github/workflows/taskops-first-run-complete.yml` (locks checklist + opens “✅ First-Run Completed” issue)

## HCB Export
- **Export (manual/scheduled)**: `.github/workflows/export-hcb.yml`, `.github/workflows/export-hcb-weekly.yml`
- **Badge injector**: `.github/autopatch/readme-hcb-badge.patch.yml`
- **README sections**: `.github/autopatch/readme-hcb-ensure-sections.patch.yml`

## AutoPatch
- **Runner**: `.github/workflows/autopatch-apply.yml`
- **Inspector**: `.github/workflows/autopatch-inspect.yml`
- **Manifest**: `.github/autopatch/patches.yml` (see README in the same folder)
