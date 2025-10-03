# ATTIC/ — Quarantine Zone

This folder is an **auto-triage parking lot**.  
When Supercheck or Auto-Triage finds files that are:

- Forbidden in the repo root,
- Duplicates,
- Out of scope or drifting,
- Orphans with no clear owner,

…they are moved here instead of being deleted.

## Rules

- Each parked file receives an `@attic` header at the top.
- The original relative path is noted in `AUTO_TRIAGE_REPORT.md`.

## Recovery

- If a file was moved here incorrectly:
  1. Move it back to the intended folder.
  2. Remove the `@attic` header.
  3. Commit normally.

## Cleanup

- Old attic files can be pruned if confirmed obsolete.
- This folder itself should never be deleted — it is part of the self-healing loop.
