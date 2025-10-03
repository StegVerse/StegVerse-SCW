#!/usr/bin/env bash
# Ensures standard sections exist; appends if missing. Idempotent via markers per section.
set -euo pipefail
FILE="${1:-README.md}"
[ -f "$FILE" ] || exit 0

insert_section () {
  local anchor="$1" ; shift
  local title="$1" ; shift
  local body="$*"

  local open="<!-- autopatch:section:${anchor}:start -->"
  local close="<!-- autopatch:section:${anchor}:end -->"

  if grep -q "$open" "$FILE"; then
    echo "AutoPatch: section '${anchor}' already present"
    return 0
  fi

  {
    echo ""
    echo "$open"
    echo "## $title"
    echo ""
    printf "%s\n" "$body"
    echo ""
    echo "$close"
  } >> "$FILE"
  echo "AutoPatch: appended section '${anchor}'"
}

insert_section "overview" "Overview" "Short project description. Replace this paragraph."
insert_section "quick-start" "Quick Start" "1) Clone, 2) Configure env, 3) Run dev server, 4) Visit UI."
insert_section "workflows" "Key Workflows" "- Supercheck, - Universal Fix-It, - Nightly Snapshot, - Rebuild Kit."
insert_section "self-healing" "Self-Healing" "Explains YAML corrector, repo audit, drift, auto-triage."
insert_section "troubleshooting" "Troubleshooting" "Common issues & fixes. Link to artifacts."
insert_section "links" "Links" "- Actions tab, - QuickTriggers page, - Docs folder."
