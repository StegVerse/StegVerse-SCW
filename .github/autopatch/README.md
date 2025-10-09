# AutoPatch Area

This folder holds **patch specifications** and the **manifest** that tells a runner which patches to apply.

## Key files

- `patches.yml` — the **manifest** (list of patch files to apply).
- `*.patch.yml` — individual patch specs (idempotent actions: write_files, run_shell, commit).
- `patches_deferred.yml` (optional) — where some runners record deferred items.

## Which runner applies this manifest?

AutoPatch can be applied by **any** of these workflows/scripts (depending on what the repo has):

- `.github/workflows/autopatch-apply.yml` → reads `.github/autopatch/patches.yml`
- `.github/workflows/AutoPatch.yml` (or `auto_patch.yml`) → usually calls `scripts/autopatch_runner.py`
- `.github/workflows/self_repair_autopatch.yml` → self-healing flavor
- `scripts/autopatch_runner.py` → Python runner that accepts `--manifest ...`
- `scripts/auto_patch.py` → legacy runner that reads `patches/manifest.json` (different system)

> 👉 Run the **Inspector** workflow (`autopatch-inspect`) to see what exists in this repo *right now* and which manifest each runner uses.

## How to run a patch

- **Manual:** Actions → `autopatch-apply` → Run workflow.
- **Auto:** push a change under `.github/autopatch/**` (if the runner workflow has a `push` path filter).

## Best practices

- Keep patches **small** and **idempotent**.
- Put a **marker file** in your patch (e.g., `.applied_xyz`) if you want an easy “was this applied?” check.
- Add a short comment header to `patches.yml` explaining what’s enabled and why (see example in that file).
