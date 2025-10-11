# AutoPatch Sentinel

Committing any file in this folder triggers the **autopatch-apply** workflow (via `push` on `main`).

## Usage
- Create or update a file here, e.g.:

echo “kick $(date -u +%FT%TZ)” > .github/trigger/autopatch/ping-$(date +%s)
