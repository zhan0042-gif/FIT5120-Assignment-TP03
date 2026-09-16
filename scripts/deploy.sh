#!/usr/bin/env bash
# Server-side deploy runbook.
#
# Started in the background by .github/workflows/deploy.yml (via AWS SSM)
# and runs to completion detached from the SSM session. It writes a status
# file that the workflow polls:
#   /var/log/fit5120-deploy.status   -> "0" on success, non-zero on failure
# All output goes to /var/log/fit5120-deploy.log (attached by the workflow).

set -uo pipefail

REPO=/home/ubuntu/FIT5120-Assignment-TP03
STATUS=/var/log/fit5120-deploy.status
LOG=/var/log/fit5120-deploy.log

# Clear the previous run's status. Do NOT write a placeholder value here: the
# workflow polls this file, and any value written before the deploy finishes
# would be read as the result of a deploy that has not run yet.
rm -f "$STATUS"

# Everything below runs inside a subshell with errexit enabled.
#
# This matters more than it looks. The previous version wrapped the same body
# in a function and called it as `if run_deploy; then ...`, and bash disables
# errexit for the entire body of a function invoked as an `if` condition. The
# failed `git pull` was therefore ignored, and the function's exit status came
# from its last command (`curl ... /api/health`, which returns 200 regardless).
# The deploy reported success while shipping stale code. A subshell has no such
# trap: errexit applies inside it, and its real exit status reaches the parent.
(
  set -euo pipefail

  export HOME=/root
  cd "$REPO"
  git config --global --add safe.directory "$REPO"

  # Disposable checkout: never `git pull --ff-only`. A force-pushed upstream
  # leaves the local branch diverged, and --ff-only can never recover from that
  # state, so the server would stay stuck on old code forever. Resetting to
  # origin/main always converges.
  git fetch --prune origin
  git reset --hard origin/main

  # Record which commit is about to be deployed. Without this line, working out
  # what production was actually running took reading the git reflog.
  echo "=== Deploying commit $(git rev-parse --short HEAD): $(git log -1 --format=%s) ==="

  # Build and run the disposable migration job before replacing Backend. The
  # job uses the same RDS environment as Backend, while keeping PyArrow out of
  # the long-running application image. Any non-zero exit stops this subshell,
  # so the currently running Backend remains active on migration failure.
  docker compose --profile migration build migration
  docker compose --profile migration run --rm --no-deps migration schema
  docker compose --profile migration run --rm --no-deps migration data

  # Production uses RDS, so do not start the local-development MySQL service.
  # Wait for the Backend healthcheck before continuing with the frontend.
  docker compose up -d --build --no-deps --wait --wait-timeout 120 backend
  # Keep the disk healthy across many deploys: drops dangling images and any
  # detached build cache that rebuilds leave behind.
  docker system prune -f

  cd frontend
  npm ci
  npm run build
  cp -r dist/. /var/www/html/

  curl -fsS http://localhost:8000/api/health

  # Assert the deploy landed on the commit it was meant to. A green deploy must
  # mean "this commit is live", not merely "the script happened to run".
  cd "$REPO"
  HEAD_SHA=$(git rev-parse HEAD)
  ORIGIN_SHA=$(git rev-parse origin/main)
  if [ "$HEAD_SHA" != "$ORIGIN_SHA" ]; then
    echo "FAILED: HEAD ($HEAD_SHA) != origin/main ($ORIGIN_SHA)"
    exit 1
  fi

  echo "=== Deploy OK: $HEAD_SHA ==="
)
STATUS_CODE=$?
echo "$STATUS_CODE" > "$STATUS"

if [ "$STATUS_CODE" -eq 0 ]; then
  echo "deploy finished OK"
else
  echo "deploy failed with exit code $STATUS_CODE (see log: $LOG)"
  exit "$STATUS_CODE"
fi
