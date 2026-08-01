#!/usr/bin/env bash
# Consistent snapshot of a Chroma store, with checksum verification.
#
# Uses `sqlite3 .backup` rather than `cp` — cp of a live SQLite file can capture a
# torn page. Refuses to run inside the weekday cron window that writes the shared
# production store (Mon-Fri 07:00, see audit E29).
set -euo pipefail

SRC="${1:?usage: backup_chroma.sh <path/to/chroma.sqlite3> [dest_dir]}"
DEST_DIR="${2:-$(dirname "$0")/../var/backups}"

dow=$(date +%u); hour=$(date +%H)
if [ "$dow" -le 5 ] && [ "$hour" = "06" -o "$hour" = "07" ]; then
  echo "REFUSED: inside the Mon-Fri 06:00-08:00 cron write window." >&2
  exit 2
fi

stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="$DEST_DIR/$stamp"
mkdir -p "$out"

sqlite3 "file:$SRC?mode=ro" ".backup '$out/chroma.sqlite3'"
sha256sum "$out/chroma.sqlite3" > "$out/chroma.sqlite3.sha256"
sha256sum -c "$out/chroma.sqlite3.sha256"

echo "backup: $out/chroma.sqlite3"
echo "verify restore before trusting it:"
echo "  sqlite3 'file:$out/chroma.sqlite3?mode=ro' 'SELECT name FROM collections;'"
