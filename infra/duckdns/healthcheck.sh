#!/bin/sh
# Healthy when the last successful DuckDNS update is under 15 minutes old.
[ -f /tmp/last-success ] || exit 1
age=$(( $(date +%s) - $(cat /tmp/last-success) ))
[ "$age" -lt 900 ]
