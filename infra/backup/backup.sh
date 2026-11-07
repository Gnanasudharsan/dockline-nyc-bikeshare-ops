#!/bin/sh
# Nightly logical backups of the warehouse and Dagster databases, with rotation.
#
# Runs inside the TimescaleDB image (same pg_dump major version as the server).
# - Every night at BACKUP_HOUR (local time): pg_dump -Fc of each database into
#   /backups/daily/<db>-<timestamp>.dump, written to a temp name and renamed when done.
# - On Sundays the warehouse dump is also copied to /backups/weekly/.
# - Keeps BACKUP_KEEP_DAILY daily and BACKUP_KEEP_WEEKLY weekly dumps per database.
# - Writes /backups/last-success (epoch seconds) for the healthcheck.
# BACKUP_ON_START=1 also takes one backup immediately; BACKUP_ONCE=1 takes one and exits
# (make backup-now).
set -eu

BACKUP_DIR=${BACKUP_DIR:-/backups}
BACKUP_HOUR=${BACKUP_HOUR:-3}
KEEP_DAILY=${BACKUP_KEEP_DAILY:-7}
KEEP_WEEKLY=${BACKUP_KEEP_WEEKLY:-4}
DATABASES="${POSTGRES_DB:-dockline} ${DAGSTER_POSTGRES_DB:-dagster}"
export PGHOST=${POSTGRES_HOST:-timescaledb} PGPORT=${POSTGRES_PORT:-5432} PGUSER=${POSTGRES_USER:-dockline}
export PGPASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) backup $*"; }

prune() {
  # Keep the newest $2 files matching $1 (a glob); delete the rest.
  # shellcheck disable=SC2086
  ls -1t $1 2>/dev/null | tail -n +"$(( $2 + 1 ))" | while read -r old; do
    log "removing $old"
    rm -f -- "$old"
  done
}

backup_once() {
  mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"
  stamp=$(date +%Y%m%d-%H%M)
  for db in $DATABASES; do
    target="$BACKUP_DIR/daily/$db-$stamp.dump"
    log "dumping $db"
    pg_dump --format=custom --compress=6 --no-owner --dbname="$db" --file="$target.partial"
    mv "$target.partial" "$target"
    log "wrote $target ($(du -h "$target" | cut -f1))"
    if [ "$(date +%u)" = "7" ]; then
      cp "$target" "$BACKUP_DIR/weekly/"
    fi
    prune "$BACKUP_DIR/daily/$db-*.dump" "$KEEP_DAILY"
    prune "$BACKUP_DIR/weekly/$db-*.dump" "$KEEP_WEEKLY"
  done
  date +%s > "$BACKUP_DIR/last-success"
}

seconds_until_next_run() {
  now=$(date +%s)
  today_run=$(date -d "$(date +%Y-%m-%d) $BACKUP_HOUR:30" +%s)
  if [ "$now" -lt "$today_run" ]; then
    echo $(( today_run - now ))
  else
    echo $(( today_run + 86400 - now ))
  fi
}

if [ "${BACKUP_ONCE:-0}" = "1" ]; then
  backup_once
  exit 0
fi
if [ "${BACKUP_ON_START:-0}" = "1" ] || [ ! -f "$BACKUP_DIR/last-success" ]; then
  backup_once || log "FAILED"
fi
while true; do
  wait_seconds=$(seconds_until_next_run)
  log "next backup in ${wait_seconds}s"
  sleep "$wait_seconds"
  backup_once || log "FAILED"
done
