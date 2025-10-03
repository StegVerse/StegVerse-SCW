#!/usr/bin/env bash
# Ensures the first Markdown H1 in README equals the desired title.
# - Desired title is, by default, the repository name (owner/name -> "name").
# - You can override via env var README_TITLE, or make it "pretty" by
#   setting README_TITLE_PRETTY=1 (kebab/snake -> Title Case).
# - Idempotent: makes no change if already correct.
set -euo pipefail

FILE="${1:-README.md}"
[ -f "$FILE" ] || exit 0

REPO="${GITHUB_REPOSITORY:-}"
NAME_FROM_REPO="${REPO##*/}"

desired_title="${README_TITLE:-$NAME_FROM_REPO}"

pretty() {
  # turn "my-cool_repo" -> "My Cool Repo"
  # keep existing capitalization if the token is all-caps (e.g. "SCW")
  awk '
    function titlecase(tok,   first, rest) {
      if (tok ~ /^[A-Z0-9]+$/) { return tok }  # SCW -> SCW
      first = toupper(substr(tok,1,1))
      rest  = tolower(substr(tok,2))
      return first rest
    }
    {
      gsub(/[-_]+/," ");
      n=split($0, a, /[ ]+/);
      out="";
      for(i=1;i<=n;i++){ out = out (i>1?" ":"") titlecase(a[i]); }
      print out
    }' <<<"$1"
}

if [ "${README_TITLE_PRETTY:-0}" = "1" ]; then
  desired_title="$(pretty "$desired_title")"
fi

MARK="<!-- autopatch:readme-title -->"
TMP="$FILE.autopatch.tmp"

# Extract current first H1 (line starting with '# ').
current_h1="$(awk '/^# /{print; exit}' "$FILE" | sed 's/^# //')"

if [ -z "$current_h1" ]; then
  # No H1 found — prepend one, but try to respect front-matter if present
  if head -n1 "$FILE" | grep -qE '^---\s*$'; then
    # YAML front matter: insert after front matter block
    awk -v title="$desired_title" -v mark="$MARK" '
      BEGIN{inheader=0; printed=0}
      NR==1 && $0 ~ /^---\s*$/ { inheader=1 }
      { print }
      inheader && $0 ~ /^---\s*$/ && NR>1 && !printed { 
        print ""; print "# " title; print mark; print ""; 
        printed=1; inheader=0
      }
    ' "$FILE" > "$TMP"
  else
    {
      echo "# $desired_title"
      echo "$MARK"
      echo ""
      cat "$FILE"
    } > "$TMP"
  fi
  mv "$TMP" "$FILE"
  echo "AutoPatch: added H1 to $FILE -> \"$desired_title\""
  exit 0
fi

# H1 exists — normalize if needed
if [ "$current_h1" = "$desired_title" ]; then
  # Ensure the marker is present right after the H1; if not, add it.
  awk -v title="$desired_title" -v mark="$MARK" '
    BEGIN{fixed=0}
    NR==1 && $0 ~ "^# "title"$" { print; next }
    $0 ~ "^# "title"$" && fixed==0 { print; getline nextline; 
      if (nextline != mark) { print mark; print nextline } else { print nextline }
      fixed=1; next
    }
    { print }
  ' "$FILE" > "$TMP"
  if cmp -s "$FILE" "$TMP"; then
    rm -f "$TMP"
    echo "AutoPatch: H1 already correct (no change) in $FILE"
  else
    mv "$TMP" "$FILE"
    echo "AutoPatch: ensured marker under existing H1 in $FILE"
  fi
  exit 0
fi

# Replace the first H1 line with desired title and ensure marker below it.
awk -v title="$desired_title" -v mark="$MARK" '
  BEGIN{done=0}
  {
    if (!done && $0 ~ /^# /) {
      print "# " title
      print mark
      done=1
      # If next line is the old marker, skip it (avoid duplicates)
      next
    }
    print
  }
' "$FILE" > "$TMP"

mv "$TMP" "$FILE"
echo "AutoPatch: replaced H1 in $FILE -> \"$desired_title\""
