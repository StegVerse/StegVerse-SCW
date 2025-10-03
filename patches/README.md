# patches/ — AutoPatch Rules

This folder contains **lightweight, incremental patch rules** for our CI workflows.
The patches are applied by `scripts/auto_patch.py` (via `.github/workflows/auto_patch.yml`).

## Why this exists

- Keep the main workflows lean and consistent without hand-editing each time.
- Roll out **small fixes** and **insert missing steps** across repos safely.
- Idempotent: re-running leaves already-correct files unchanged.

## Files

- `manifest.json` — list of ordered patch rules; each rule targets files using `target_glob`.
  - `replace.find_regex` with `with_text`: fixes known blocks in-place.
  - `if_absent.anchor_regex` with `position` + `insert_text`: injects content if missing.

## How to run

- Manually: run the **Auto Patch** workflow in GitHub Actions (or commit to `.github/trigger/autopatch/`).
- Automatically: it also runs from **One-Button Supercheck** early, so fixes land before other audits.

## Adding a new rule

1. Add a new object to `patches/manifest.json` with a unique `id`.
2. Use a narrow `target_glob` (e.g., `.github/workflows/*supercheck*.yml`).
3. Prefer an **anchor-based `if_absent`** insert when possible (safer than broad regex replacements).
4. Commit to `main` to trigger autopatch (if push path filter is configured).

## Safety

- Patches are meant to be **surgical** and **small**.
- If a patch would result in duplicate blocks, it won’t apply (anchor detection fails).
- Everything is logged as an artifact in the **Auto Patch** run.
