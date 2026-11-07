#!/bin/sh
# Healthy when the last successful backup is less than 26 hours old.
last=$(cat "${BACKUP_DIR:-/backups}/last-success" 2>/dev/null || echo 0)
[ $(( $(date +%s) - last )) -lt 93600 ]
