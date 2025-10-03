#!/usr/bin/env bash
set -euo pipefail

FILE="${1:-}"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "AutoPatch: file not found: $FILE" >&2
  exit 0
fi

REPO="${GITHUB_REPOSITORY:-}"
if [ -z "$REPO" ]; then
  echo "AutoPatch: GITHUB_REPOSITORY not set; skipping $FILE" >&2
  exit 0
fi

TMP="$FILE.autopatch.tmp"

# Rewrite common GitHub links inside issue templates:
# - issues/new, issues, pulls, discussions, actions links pointing to old repos
# - raw "github.com/owner/name" repo links
awk -v repo="$REPO" '
{
  # Issues (new + list)
  gsub(/github\.com\/[^\/]+\/[^\/]+\/issues\/new/,      "github.com/" repo "/issues/new")
  gsub(/github\.com\/[^\/]+\/[^\/]+\/issues/,           "github.com/" repo "/issues")

  # Pull requests
  gsub(/github\.com\/[^\/]+\/[^\/]+\/pulls/,            "github.com/" repo "/pulls")
  gsub(/github\.com\/[^\/]+\/[^\/]+\/pull\/[0-9]+/,     "github.com/" repo "/pull/&")  # keep /pull/<n>

  # Discussions
  gsub(/github\.com\/[^\/]+\/[^\/]+\/discussions/,      "github.com/" repo "/discussions")

  # Actions (workflows)
  gsub(/github\.com\/[^\/]+\/[^\/]+\/actions\/workflows\//, "github.com/" repo "/actions/workflows/")

  # General bare repo links
  gsub(/github\.com\/[^\/]+\/[^\/]+(\.git)?/,           "github.com/" repo "\\1")

  print
}' "$FILE" > "$TMP"

if cmp -s "$FILE" "$TMP"; then
  rm -f "$TMP"
  echo "AutoPatch: $FILE unchanged (no template link patterns matched)"
else
  mv "$TMP" "$FILE"
  echo "AutoPatch: normalized issue-template links in $FILE -> $REPO"
fi
