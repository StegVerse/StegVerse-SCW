#!/usr/bin/env bash
set -euo pipefail

FILE="${1:-README.md}"
[ -f "$FILE" ] || exit 0

REPO="${GITHUB_REPOSITORY:-}"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
MARK="<!-- maintained-by-stegverse -->"

# If footer already exists, refresh minimal bits; else append at EOF.
if grep -q "$MARK" "$FILE"; then
  # Refresh the timestamp line only (keep any local edits around it).
  awk -v now="$NOW" -v repo="$REPO" -v mark="$MARK" '
    BEGIN{block=0}
    {
      if ($0 ~ mark) { block=1; print; next }
      if (block==1 && $0 ~ /^_Last checked:/) {
        print "_Last checked: " now " (UTC)_  "
        block=0; next
      }
      print
    }
  ' "$FILE" > "$FILE.autopatch.tmp"
  if cmp -s "$FILE" "$FILE.autopatch.tmp"; then
    rm -f "$FILE.autopatch.tmp"
    echo "AutoPatch: footer present (no change) in $FILE"
  else
    mv "$FILE.autopatch.tmp" "$FILE"
    echo "AutoPatch: footer timestamp refreshed in $FILE"
  fi
  exit 0
fi

cat >> "$FILE" <<EOF

---

$MARK  
<p align="center">
  <sub>Maintained by <a href="https://github.com/\${GITHUB_REPOSITORY}">\${GITHUB_REPOSITORY}</a></sub><br/>
  <sub>_Last checked: ${NOW} (UTC)_</sub>
</p>
EOF

echo "AutoPatch: footer appended to $FILE"
