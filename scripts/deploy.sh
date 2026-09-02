#!/usr/bin/env bash
# Server-side deploy runbook.
#
# Started in the background by .github/workflows/deploy.yml (via AWS SSM)
# and runs to completion detached from the SSM session. It writes a status
# file that the workflow polls:
#   /var/log/fit5120-deploy.status   -> "0" on success, non-zero on failure
# All output goes to /var/log/fit5120-deploy.log (attached by the workflow).

set -u

REPO=/home/ubuntu/FIT5120-Assignment-TP03
STATUS=/var/log/fit5120-deploy.status
LOG=/var/log/fit5120-deploy.log

rm -f "$STATUS"

run_deploy() {
  set -e
  export HOME=/root
  cd "$REPO"

  git config --global --add safe.directory "$REPO"
  git pull --ff-only origin main

  docker compose up -d --build --no-deps backend
  docker image prune -f

  cd frontend
  npm ci
  npm run build
  cp -r dist/. /var/www/html/

  curl -fsS http://localhost:8000/api/health
}

if run_deploy; then
  STATUS_CODE=0
else
  STATUS_CODE=$?
fi

echo "$STATUS_CODE" > "$STATUS"

if [ "$STATUS_CODE" -eq 0 ]; then
  echo "deploy finished OK"
else
  echo "deploy failed with exit code $STATUS_CODE (see log: $LOG)"
  exit "$STATUS_CODE"
fi
