#!/bin/sh
# Keep the DuckDNS subdomains pointed at this VM's public IP.
# DuckDNS detects the caller's address when ip= is empty. Runs every
# DUCKDNS_INTERVAL seconds; records the last success for the healthcheck.
# The token is never printed.
set -u

: "${DUCKDNS_DOMAINS:?Set DUCKDNS_DOMAINS (comma-separated, without .duckdns.org)}"
: "${DUCKDNS_TOKEN:?Set DUCKDNS_TOKEN}"
INTERVAL="${DUCKDNS_INTERVAL:-300}"

while true; do
    result=$(curl -fsS --max-time 30 \
        "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAINS}&token=${DUCKDNS_TOKEN}&ip=" 2>/dev/null)
    if [ "$result" = "OK" ]; then
        date +%s > /tmp/last-success
        echo "{\"level\":\"info\",\"event\":\"duckdns_updated\",\"domains\":\"${DUCKDNS_DOMAINS}\"}"
    else
        echo "{\"level\":\"error\",\"event\":\"duckdns_update_failed\",\"domains\":\"${DUCKDNS_DOMAINS}\"}"
    fi
    sleep "$INTERVAL"
done
