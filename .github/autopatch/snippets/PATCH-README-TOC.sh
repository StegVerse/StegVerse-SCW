#!/usr/bin/env bash
# Generates a simple TOC from H2/H3 headings, inserted below H1. Idempotent.
set -euo pipefail
FILE="${1:-README.md}"
[ -f "$FILE" ] || exit 0

OPEN="<!-- autopatch:toc:start -->"
CLOSE="<!-- autopatch:toc:end -->"

toc="$(awk '
  BEGIN{ inbody=0 }
  /^# /{ inbody=1; next }       # skip the H1 itself
  inbody && /^##+ /{
    level=gsub(/^#+ /,""); t=$0;
    anchor=t; gsub(/[^a-zA-Z0-9 _-]/,"",anchor);
    gsub(/[ ]+/,"-",anchor); anchor=tolower(anchor);
    if (level==2) printf("- [%s](#%s)\n", t, anchor);
    if (level==3) printf("  - [%s](#%s)\n", t, anchor);
  }' "$FILE")"

block="$OPEN
**Table of contents**
$toc
$CLOSE"

if grep -q "$OPEN" "$FILE"; then
  awk -v open="$OPEN" -v close="$CLOSE" -v block="$block" '
    BEGIN{inb=0}
    {
      if ($0==open){ inb=1; print block; next }
      if (inb && $0==close){ inb=0; next }
      if (!inb) print
    }' "$FILE" > "$FILE.autopatch.tmp"
  mv "$FILE.autopatch.tmp" "$FILE"
  echo "AutoPatch: refreshed TOC"
else
  awk -v block="$block" '
    BEGIN{done=0}
    {
      print
      if (!done && $0 ~ /^# /){ print ""; print block; print ""; done=1 }
    }' "$FILE" > "$FILE.autopatch.tmp"
  mv "$FILE.autopatch.tmp" "$FILE"
  echo "AutoPatch: inserted TOC"
fi
