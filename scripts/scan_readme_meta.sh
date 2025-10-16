#!/usr/bin/env bash
set -euo pipefail
FILE="${1:-README.md}"
jq -n --arg h1 "$(awk '/^# /{print substr($0,3); exit}' "$FILE" 2>/dev/null)" \
      --arg badges "$(grep -q '<!-- autopatch:badges:start -->' "$FILE" && echo yes || echo no)" \
      --arg toc "$(grep -q '<!-- autopatch:toc:start -->' "$FILE" && echo yes || echo no)" \
      '{h1:$h1,badges:($badges=="yes"),toc:($toc=="yes")}'
