#!/usr/bin/env bash
# Acceptance test: stopping ingestion must fire the "Feed stale" alert.
#
# Stops the ingestion service, polls Grafana until the dockline-feed-stale rule is
# firing (or a timeout), then ALWAYS restarts ingestion and waits for the rule to
# recover. Expect ~6 minutes to fire (300 s threshold + 1 m pending + evaluation)
# and a short gap in raw history (GBFS only publishes the current state).
#
# Usage: make test-stale-alert   (reads GRAFANA_* from .env)
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

GRAFANA_URL="http://localhost:${GRAFANA_PORT:-3060}"
AUTH="${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-720}"

rule_state() {
  curl -s -u "$AUTH" "$GRAFANA_URL/api/prometheus/grafana/api/v1/rules" | python3 -c '
import json, sys
for group in json.load(sys.stdin)["data"]["groups"]:
    for rule in group["rules"]:
        if rule["name"].startswith("Feed stale"):
            print(rule["state"])
'
}

restart_ingestion() {
  echo "$(date +%T) restarting ingestion"
  docker compose start ingestion >/dev/null
}
trap restart_ingestion EXIT

echo "$(date +%T) feed-stale rule state before: $(rule_state)"
echo "$(date +%T) stopping ingestion"
docker compose stop ingestion >/dev/null

start=$(date +%s)
fired=""
while (( $(date +%s) - start < TIMEOUT_SECONDS )); do
  state=$(rule_state)
  if [[ "$state" == "firing" ]]; then
    fired=$(( $(date +%s) - start ))
    echo "$(date +%T) FIRED after ${fired}s"
    break
  fi
  sleep 15
done

restart_ingestion
trap - EXIT

if [[ -z "$fired" ]]; then
  echo "FAIL: feed-stale alert did not fire within ${TIMEOUT_SECONDS}s"
  exit 1
fi

start=$(date +%s)
while (( $(date +%s) - start < 600 )); do
  if [[ "$(rule_state)" == "inactive" ]]; then
    echo "$(date +%T) recovered after $(( $(date +%s) - start ))s"
    exit 0
  fi
  sleep 15
done
echo "WARN: alert fired but had not recovered 10 minutes after restart"
exit 1
