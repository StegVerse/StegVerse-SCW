#!/usr/bin/env bash
set -euo pipefail

# Target file is passed as $1 (AutoPatch calls this script per matched file)
FILE="${1:-README.md}"

# Resolve the current <owner>/<repo>
REPO="${GITHUB_REPOSITORY:-}"
if [ -z "$REPO" ]; then
  echo "AutoPatch: GITHUB_REPOSITORY not set; skipping $FILE" >&2
  exit 0
fi
OWNER="${REPO%%/*}"
NAME="${REPO##*/}"

TMP="$FILE.autopatch.tmp"

# Normalize common badge/link patterns to current repo
awk -v repo="$REPO" -v owner="$OWNER" -v name="$NAME" '
{
  # GitHub Actions badge (badge + link)
  gsub(/github\.com\/[^\/]+\/[^\/]+\/actions\/workflows\//,
       "github.com/" repo "/actions/workflows/")

  # Shields “workflow status”
  gsub(/github\/actions\/workflow\/status\/[^\/]+\/[^\/]+\//,
       "github/actions/workflow/status/" repo "/")

  # Shields generic GitHub stats (issues, stars, forks, last-commit, etc.)
  gsub(/img\.shields\.io\/github\/issues\/[^\/]+\/[^\/]+/,
       "img.shields.io/github/issues/" repo)
  gsub(/img\.shields\.io\/github\/stars\/[^\/]+\/[^\/]+/,
       "img.shields.io/github/stars/" repo)
  gsub(/img\.shields\.io\/github\/forks\/[^\/]+\/[^\/]+/,
       "img.shields.io/github/forks/" repo)
  gsub(/img\.shields\.io\/github\/last-commit\/[^\/]+\/[^\/]+/,
       "img.shields.io/github/last-commit/" repo)

  # Badgen GitHub stats
  gsub(/badgen\.net\/github\/issues\/[^\/]+\/[^\/]+/,
       "badgen.net/github/issues/" repo)
  gsub(/badgen\.net\/github\/stars\/[^\/]+\/[^\/]+/,
       "badgen.net/github/stars/" repo)
  gsub(/badgen\.net\/github\/forks\/[^\/]+\/[^\/]+/,
       "badgen.net/github/forks/" repo)

  # Coveralls classic
  gsub(/coveralls\.io\/repos\/github\/[^\/]+\/[^\/]+\//,
       "coveralls.io/repos/github/" repo "/")

  # Codecov
  gsub(/codecov\.io\/gh\/[^\/]+\/[^\/]+/,
       "codecov.io/gh/" repo)

  # General GitHub repo links
  gsub(/github\.com\/[^\/]+\/[^\/]+(\.git)?/,
       "github.com/" repo "\\1")

  print
}' "$FILE" > "$TMP"

if cmp -s "$FILE" "$TMP"; then
  rm -f "$TMP"
  echo "AutoPatch: $FILE unchanged (no badge/link patterns matched)"
else
  mv "$TMP" "$FILE"
  echo "AutoPatch: normalized badges/links in $FILE -> $REPO"
fi
