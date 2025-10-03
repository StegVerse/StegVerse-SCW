#!/usr/bin/env bash
set -euo pipefail
DEPTH="${1:-3}"
IGNORE="${2:-node_modules|.git|__pycache__|venv|dist|build}"

echo "# Repository Structure"
echo
echo '```'

if command -v tree >/dev/null 2>&1; then
  tree -I "${IGNORE}" -L "${DEPTH}" --charset ascii || true
else
  find . -type d -maxdepth "${DEPTH}" \
    | grep -Ev "/(${IGNORE//|/|})($|/)" \
    | sed 's|^\./||' \
    | awk -F'/' '{
        indent = length($0)-length(gensub("[^/]","","g",$0))
        prefix = ""
        for(i=0;i<indent;i++){prefix=prefix "  "}
        print prefix $NF
      }'
  echo
  echo "(Fallback renderer used — install 'tree' for nicer output.)"
fi

echo '```'
echo
echo "Last updated: $(date -u '+%Y-%m-%d %H:%M:%S %Z')"
