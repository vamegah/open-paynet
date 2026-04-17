#!/usr/bin/env sh
set -eu

ACTION="${1:-backup}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
STAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
BACKUP_FILE="${2:-$BACKUP_DIR/ledger-$STAMP.sql}"

mkdir -p "$BACKUP_DIR"

case "$ACTION" in
  backup)
    echo "Creating Postgres backup at $BACKUP_FILE"
    pg_dump --clean --if-exists --no-owner --no-privileges --format=plain --file="$BACKUP_FILE"
    echo "Backup complete: $BACKUP_FILE"
    ;;
  restore)
    if [ ! -f "$BACKUP_FILE" ]; then
      echo "Backup file not found: $BACKUP_FILE" >&2
      exit 1
    fi
    echo "Restoring Postgres backup from $BACKUP_FILE"
    psql --dbname=postgres --command="SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'ledger' AND pid <> pg_backend_pid();"
    psql --dbname=postgres --command="DROP DATABASE IF EXISTS ledger;"
    psql --dbname=postgres --command="CREATE DATABASE ledger;"
    psql --dbname=ledger --file="$BACKUP_FILE"
    echo "Restore complete from $BACKUP_FILE"
    ;;
  *)
    echo "Unsupported action: $ACTION" >&2
    exit 1
    ;;
esac
