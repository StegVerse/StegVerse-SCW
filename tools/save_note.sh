#!/usr/bin/env bash
set -euo pipefail
TITLE="${1:-}"
FILETXT="${2:-}"
if [[ -z "$TITLE" || -z "$FILETXT" ]]; then
  echo "Usage: tools/save_note.sh \"Title here\" path/to/text_or_md_file"
  exit 1
fi

mkdir -p docs/conversations
TS=$(date -u +"%Y%m%d-%H%M%S")
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-|-$//g')
OUT="docs/conversations/${TS}-${SLUG}.md"
DATE_LOCAL=$(date +"%Y-%m-%d %H:%M")

{
  echo "---"
  echo "title: \"$TITLE\""
  echo "date: \"$DATE_LOCAL\""
  echo "participants: [\"Rigel\", \"Assistant\"]"
  echo "tags: []"
  echo "---"
  echo
  echo "# Next actions (resume here)"
  echo "- [ ] <fill me>"
  echo
  echo "# Decisions / agreements"
  echo "- <fill me>"
  echo
  echo "# Open questions"
  echo "- <fill me>"
  echo
  echo "# Notes"
  cat "$FILETXT"
  echo
} > "$OUT"

INDEX="docs/conversations/INDEX.md"
test -f "$INDEX" || echo "# Conversation Index" > "$INDEX"
printf -- "- %s – **%s** → [open](%s)\n\n" "$(date +"%Y-%m-%d %H:%M")" "$TITLE" "$OUT" | cat - "$INDEX" > "$INDEX.new"
mv "$INDEX.new" "$INDEX"

git add "$OUT" "$INDEX"
git commit -m "notes: $TITLE"
git push
echo "Saved to $OUT"
