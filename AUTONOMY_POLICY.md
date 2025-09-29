# Autonomy Policy (Supercheck)

## Principles
- **Preserve first**: never permanently delete by default; move to `ATTIC/` with context.
- **Explain every action**: each run uploads `supercheck_report.md` + machine JSONs.
- **Reproducible**: after changes, a Rebuild Kit should be generated (future step).

## Actions
- Scaffold missing *required* dirs/files with placeholders.
- Remove *forbidden* items (e.g., secrets, certs) immediately.
- Move *extras* (not required/recommended) to `ATTIC/` with an `@attic` header.
- Keep *recommended* files (create if missing).
- If `auto_commit = false`, changes are proposed via PR.

## Future extensions
- Train a lightweight classifier from past Keep/ATTIC decisions.
- Auto-merge PRs when Smoke/Diag tests pass.
- Tie changes to ADRs and Ideas with `[topic:<tag>]` commit tags.
