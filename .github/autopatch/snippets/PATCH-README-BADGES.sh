#!/usr/bin/env bash
# Dry-run: report what we'd set the README H1 to, but do not modify files.
set -euo pipefail

FILE="${1:-README.md}"
[ -f "$FILE" ] || { echo "DRYRUN: $FILE not found"; exit 0; }

REPO="${GITHUB_REPOSITORY:-}"
NAME_FROM_REPO="${REPO##*/}"
desired="${README_TITLE:-$NAME_FROM_REPO}"

if [ "${README_TITLE_PRETTY:-0}" = "1" ]; then
  desired="$(awk '{
    gsub(/[-_]+/," ");
    n=split($0,a," ");
    o=""; for(i=1;i<=n;i++){ tok=a[i];
      if (tok ~ /^[A-Z0-9]+$/) { o=o (i>1?" ":"") tok; }
      else { o=o (i>1?" ":"") toupper(substr(tok,1,1)) tolower(substr(tok,2)); }
    } print o
  }' <<<"$desired")"
fi

current="$(awk '/^# /{print; exit}' "$FILE" | sed 's/^# //')"
if [ -z "$current" ]; then
  echo "DRYRUN: would add H1 \"# $desired\" to $FILE"
elif [ "$current" != "$desired" ]; then
  echo "DRYRUN: would replace H1 \"$current\" -> \"$desired\" in $FILE"
else
  echo "DRYRUN: H1 already correct in $FILE"
fi
