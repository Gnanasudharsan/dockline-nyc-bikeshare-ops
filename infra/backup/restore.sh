#!/bin/sh
# Restore a warehouse dump into a NEW database (never over the live one).
#
# Usage (from the repository root):
#   docker compose -f docker-compose.yml -f infra/docker-compose.prod.yml exec backup \
#     /scripts/restore.sh /backups/daily/dockline-YYYYMMDD-HHMM.dump dockline_restore
#
# TimescaleDB needs timescaledb_pre_restore() / timescaledb_post_restore() around
# pg_restore so hypertables and continuous aggregates come back intact.
set -eu
dump=${1:?usage: restore.sh <dump file> <new database name>}
target=${2:?usage: restore.sh <dump file> <new database name>}
export PGHOST=${POSTGRES_HOST:-timescaledb} PGPORT=${POSTGRES_PORT:-5432} PGUSER=${POSTGRES_USER:-dockline}
export PGPASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}

if psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$target'" | grep -q 1; then
  echo "Database $target already exists; choose a new name." >&2
  exit 1
fi
psql -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$target\""
psql -d "$target" -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS timescaledb" -c "SELECT timescaledb_pre_restore()"
pg_restore --dbname="$target" --no-owner --exit-on-error "$dump" || status=$?
psql -d "$target" -v ON_ERROR_STOP=1 -c "SELECT timescaledb_post_restore()"
if [ "${status:-0}" != "0" ]; then
  echo "pg_restore reported errors (exit ${status}); inspect $target before using it." >&2
  exit "$status"
fi
echo "Restored $dump into $target."
psql -d "$target" -c "SELECT count(*) AS station_status_rows FROM raw.station_status" -c "SELECT count(*) AS hourly_fact_rows FROM marts.fct_station_hourly"
