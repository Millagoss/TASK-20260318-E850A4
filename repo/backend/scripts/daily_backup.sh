#!/bin/sh
set -e

BACKUP_DIR="/app/backups"
mkdir -p "$BACKUP_DIR"

if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi
DB_URL="$DATABASE_URL"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$BACKUP_DIR/backup_${TS}.sql"

pg_dump "$DB_URL" > "$OUT_FILE"
echo "$OUT_FILE"
