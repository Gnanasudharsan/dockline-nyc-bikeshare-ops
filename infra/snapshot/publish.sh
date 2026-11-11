#!/usr/bin/env bash
# Publish a snapshot directory as the single commit of the `data` branch.
# Usage: publish.sh <dir>   (needs GH_TOKEN and GITHUB_REPOSITORY)
set -euo pipefail
dir="$1"
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$dir"
python3 - <<'PY'
import json, pathlib
for name in ("latest.json", "history-24h.json", "daily-kpis.json"):
    path = pathlib.Path(name)
    json.loads(path.read_text())
    print(f"{name}: {path.stat().st_size / 1024:.0f} KB")
PY
cp "$repo_root/infra/snapshot/DATA_BRANCH_README.md" README.md
# Vercel reads its config from the pushed commit: carry the rule that skips
# deployments of this branch.
mkdir -p web && cp "$repo_root/web/vercel.json" web/vercel.json
# A fresh repository every time, so the branch is always exactly one commit.
rm -rf .git
git init -q -b data
git config user.name "Gnanasudharsan"
git config user.email "84964314+Gnanasudharsan@users.noreply.github.com"
git add -A
git commit -q -m "chore(data): snapshot $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push -q --force "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" HEAD:data
