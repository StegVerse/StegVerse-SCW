#!/usr/bin/env bash
set -euo pipefail

# Make sure scripts dir is absolute
ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

OUTDIR="$ROOT/bundle_out"
mkdir -p "$OUTDIR"

# Name bundle with timestamp
STAMP=$(date +%Y%m%d-%H%M%S)
BASENAME="rebuild_bundle_$STAMP"

echo "==> Creating bundle at $OUTDIR/$BASENAME.zip"

# Collect key directories (adjust as needed)
zip -r "$OUTDIR/$BASENAME.zip" \
  .github/workflows \
  scripts \
  README.md \
  || true

# Symlink/copy a latest pointer for convenience
ln -sf "$BASENAME.zip" "$OUTDIR/latest.zip"

echo "==> Bundle created: $OUTDIR/$BASENAME.zip"
ls -lh "$OUTDIR"
