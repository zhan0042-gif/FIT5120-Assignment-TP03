# Deployment Plan (I1–I2)

**Project:** Shielding Crisis & Community Resilience — I1–I2.
**Owner:** Cybersecurity & Deployment Lead. **Status: IMPLEMENTED — live since 2026-09-02** (https://cubesix.me); deploy path rewritten 2026-09-13. This document describes the deployed system and the CI/CD path that keeps it updated.

## 1. Architecture (live)

One EC2 instance runs the backend as a Docker container; Nginx serves the static frontend, terminates HTTPS, and proxies `/api` to the backend. Matches the layout described in `nginx/README.md`.

Architecture (read top to bottom):

1. Internet clients reach the site over HTTPS (ports 80/443).
2. Nginx terminates HTTPS, enforces the shared-password auth gate, and:

   - `/`    serves the Vue frontend (static files)
   - `/api` proxies to the backend container
3. Backend (FastAPI / uvicorn) runs in Docker, listening on `127.0.0.1:8000`.
4. Backend reads/writes RDS (MySQL 8.4, managed), reachable only from the
   EC2 security group — never exposed to the public Internet.


Key points:

- **One EC2** keeps cost and ops simple for a student prototype (same pattern as our earlier project).
- **Database = AWS RDS (MySQL 8.4)** — managed service, never exposed publicly; the RDS security group allows MySQL from the EC2 only.
- **Nginx** terminates HTTPS and routes `/api` to FastAPI; frontend is served as static files from `/var/www/html`.
- **Auto-deploy** (see §5): merging to `main` triggers tests + a remote deploy over AWS SSM — no manual server steps for a normal release.

## 2. Components

| Component | Detail |
| --------------- | ------------------------------------------------------------------------------------- |
| **EC2** | Ubuntu 24.04, t3.micro, `i-060c00865b0bf629e` (ap-southeast-4, public `16.50.155.51`). **Access via AWS SSM Session Manager** as the normal path; **port 22 stays open but restricted to the operator's home IP** (`101.188.108.19/32`) as the emergency fallback when the SSM agent is unavailable (F5/R5 in the vulnerability assessment report). Boot volume is 20 GiB gp3, resized from 8 GiB on 2026-09-02 — the 8 GiB disk repeatedly filled up during builds (see §6 ops notes) |
| **Backend** | `backend/Dockerfile` (python:3.12-slim, uvicorn on :8000), run as a container via Docker Compose; health check at `/api/health` |
| **MySQL / RDS** | **Reusing the existing `fit5120-db`** (db.t4g.micro, MySQL 8.4). Production `DATABASE_HOST` points at the RDS endpoint; the `mysql:8.4` service in `docker-compose.yml` is local dev only. Legacy migrations through 008 were applied manually; migrations 009+ and one-time data jobs are automatic and run before Backend activation. |
| **Frontend** | Vue 3 + Vite. Production build (`npm run build`) output is copied to `/var/www/html/` |
| **Nginx** | Production config at `/etc/nginx/sites-enabled/default`: `server_name cubesix.me www.cubesix.me`; `location /` serves the static frontend, `location /api/` proxies to `127.0.0.1:8000`; **shared-password basic auth gate** covering `/` and `/api` (see §7 auth) |
| **HTTPS** | Let's Encrypt via certbot on `cubesix.me` — temporary domain; auto-renewal active |

## 3. Networking & security groups

- Inbound: **80 + 443 from 0.0.0.0/0** only.
- **Port 22 restricted to the operator's home IP** (`101.188.108.19/32`) — emergency fallback for when SSM Session Manager is unavailable; management is primarily via SSM (instance role `EC2-SSM-Role`, policy `AmazonSSMManagedInstanceCore`). Accepted operational risk (F5/R5 in the vulnerability assessment report).
- **MySQL not exposed** — RDS has public access off; reachable only from the EC2 security group.
- Outbound: apt updates, image pulls, the SSH fetch from GitHub, and external APIs (TomTom Orbis Places, TomTom Routing, CFA, BOM, NVIDIA).

## 4. Secret flow

- **Local dev** — `.env` at repo root (`chmod 600`), gitignored.
- **CI/CD** — GitHub Actions Secrets (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`) — never in workflow files.
- **Production** — `.env` on the server at the repo root, holding `TOMTOM_API_KEY` (live address lookup and routing), `AI_API_KEY` (rendezvous explanation), Backend database credentials, and separate `MIGRATION_DB_USER` / `MIGRATION_DB_PASSWORD` credentials used only by the disposable migration service. `chmod 600`, owner root — the deploy runs as root, so that ownership is harmless. Which key belongs to which account, and how each is rotated, is recorded in `secret-handling.md`.
- **Repo fetch** — the server pulls the repo via an SSH deploy key (`/root/.ssh/github_deploy`, read-only, added in the repo's Deploy Keys).
- **Site gate password** — Nginx basic-auth htpasswd file on the server only, never committed.
- **Deploy IAM** — IAM user `github-actions-deploy` (no console) with a scoped inline policy allowing only SSM `SendCommand`/invocation reads on the instance (plus `ec2:DescribeInstances`); used only by GitHub Actions.

Source of truth for variable names: `.env.example` (see `secret-handling.md`).

## 5. CI/CD path (live)

`.github/workflows/deploy.yml` runs on push/merge to `main` (paths: `backend/**`, `frontend/**`, `data/**`, `database/**`, `scripts/**`, `docker-compose.yml`, the workflow itself) and on `workflow_dispatch`.

Pipeline flow (top to bottom):

1. **Merge to main**.
2. **Job 1 — backend tests** (`pytest`): if these fail, the deploy job never runs.
3. **Job 2 — deploy to EC2 via AWS SSM**:
   1. `send-command` starts `scripts/deploy.sh` on the server in the background (setsid); its output goes to `/var/log/fit5120-deploy.log`.
   2. The workflow first awaits that kickoff command's own Status (send-command is async — polling its side-effects too early once caused a false "NO_LOG").
   3. The workflow then polls `/var/log/fit5120-deploy.status` until it reads "0" (success).
   4. It tails the log into the Actions run.

The production `deploy` job uses the stable
`firebreak-production-deployment` concurrency group with
`cancel-in-progress: false`. Backend test jobs may run concurrently, but a
production deployment waits for the active deployment and is never cancelled
while migrations may be using the shared checkout, log, or status file.


`scripts/deploy.sh` (server-side) runs inside a subshell with `set -euo pipefail` and does: `git fetch --prune origin` → `git reset --hard origin/main` → log the deployed commit → build the disposable migration image → validate its dedicated migration credentials → apply pending schema migrations → run pending one-time data migrations → `docker compose up -d --build --no-deps --wait --wait-timeout 120 backend` (RDS is external; wait for Backend health) → `docker system prune -f` (disk hygiene) → frontend `npm ci` + `npm run build` → copy `dist` to `/var/www/html/` → health-check `curl /api/health` → assert `HEAD == origin/main`.

Three details here are load-bearing, and all three were learned on 2026-09-08 (see §7 and threat-model T11):

- **The checkout is disposable.** `git pull --ff-only` fails permanently once the local branch is left diverged, and a force-pushed upstream does exactly that. A failed pull is also invisible afterwards: it writes no reflog entry, so the server simply stops updating with nothing to show for it. `git reset --hard origin/main` always converges, and `.env` is untracked, so a hard reset cannot touch it.
- **`set -e` has to actually apply.** The body runs in a subshell rather than a shell function, because bash disables `errexit` for the entire body of a function invoked as an `if` test — which is how a failing `git pull` was ignored while the script still printed "deploy finished OK". The SSM kickoff command list also begins with `set -e`, because `AWS-RunShellScript` reports only the exit code of its **last** command (`echo deploy-started`, which always succeeds).
- **Success is asserted, not assumed.** The script compares `HEAD` with `origin/main` and exits non-zero if they differ, so a green run means "this commit is live", not merely "the script ran". A container that reports `Up (healthy)` proves nothing about which code is inside it.

Why detached + polled: a single long, high-output SSM command crashes the SSM document worker (`ipc messaging received timeout signal`). Running the deploy in the background and polling a status file is the workaround. First green end-to-end run: 2026-09-02 (Actions run #5).

## 6. Deployment runbook (executed — retained for reference / rebuilds)

Steps 1–8 below were performed to bring this environment up; they are the rebuild path if the instance is ever re-created.

1. **Done (2026-09-02):** Provision EC2 (Ubuntu 24.04, t3.micro) — this instance was reused from the earlier project; SSM role attached, security groups 80/443 only.
2. **Done:** DNS `cubesix.me` → EC2 IP.
3. **Done:** Docker + Docker Compose plugin installed on the server.
4. **Done:** `.env` (real values, `DATABASE_HOST` = RDS endpoint) at repo root on the server; `chmod 600`.
5. **Done:** RDS `fit5120-db` reused; safety snapshot taken; old project's schema replaced by `database/init/001_initial_schema.sql`.
6. **Done:** `docker compose up -d --build` (no `mysql` service in prod); `/api/health` returns `{"status":"ok"}`.
7. **Done:** Nginx reverse proxy + basic auth gate + certbot HTTPS + auto-renew.
8. **In progress:** security checks in `deployment-checklist.md` are being worked through; evidence is submitted in PGP (Security folder).

**Ops notes learned during bring-up (worth keeping):**

- **SSM runs commands as root with no `HOME`** → the kickoff `export HOME=/root` and `git config --global --add safe.directory <repo>` before any git command in the repo (root operating on an ubuntu-owned repo would otherwise be a "dubious ownership" fatal).
- **Disk is the scarce resource.** The 8 GiB boot volume filled to 100% mid-deploy (killed a frontend copy with `ENOSPC`). Fixed by resizing to 20 GiB (console Modify volume → `growpart /dev/nvme0n1 1` → `resize2fs /dev/nvme0n1p1`) plus `docker system prune -f` after each build in `deploy.sh`. If disk creeps up again: `sudo df -h /`, `sudo du -xh --max-depth=1 / 2>/dev/null | sort -rh | head`, `sudo apt-get autoremove --purge -y`, `sudo journalctl --vacuum-size=20M`.
- **Deploy log / status** live on the server at `/var/log/fit5120-deploy.log` and `/var/log/fit5120-deploy.status` — the GitHub Actions "tail the log" step prints the end of the former into the run output. The log is overwritten at the start of each run, so it holds only the most recent deploy: read it before the next one. The status file is deleted when a run starts and only written when it finishes, so **a missing status file means "running, or never started"** — read the log tail or `ps aux | grep "[d]eploy.sh"` rather than concluding the deploy failed.
- **Schema migrations 009+ are automatic.** RDS never runs `database/init/` (that path only executes when a fresh volume is created). The migration job treats 001-008 as a legacy baseline, tracks newer schema and one-time data migrations by filename and checksum, and runs them before Backend activation. See `database-migrations.md`.
- **Migration credentials are separate.** Before enabling automation, the Deployment owner must confirm the RDS 001-008 baseline, create a least-privilege migration user, configure `MIGRATION_DB_USER` / `MIGRATION_DB_PASSWORD` in the protected server `.env`, review the required migration privileges (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`, `INDEX`, `REFERENCES` as applicable), and verify the migration container can connect. The Backend continues to use only `MYSQL_USER` / `MYSQL_PASSWORD`.
- **Memory needs host-level protection.** On the approximately 1 GB EC2 host, the deployment lead should add approximately 1–2 GB of swap after approval and monitor `free -h`, `docker stats --no-stream`, `docker ps`, and `docker compose ps`. Inspect kernel OOM evidence with `sudo dmesg -T | grep -i -E "out of memory|killed process|oom"` or the equivalent `sudo journalctl -k --no-pager` pipeline. Swap absorbs short spikes; `restart: unless-stopped` recovers Backend process exits. The restart policy does not prevent OOM.

## 7. Decisions (recorded)

- **Domain** — **DECIDED (temporary): `cubesix.me`** (reused from the earlier project). Swappable later via DNS + certbot (~10 min).
- **Auth model** — **DECIDED (2026-08-31): shared-password site gate.** Nginx basic auth on `/` and `/api` with one shared password; no per-user login for I1 (see `threat-model.md` T1/T2).
- **Database** — **DECIDED (2026-09-01): reuse `fit5120-db` RDS.** Old project data removed after a safety snapshot; Docker MySQL stays local-dev-only.
- **Images** — **DECIDED by implementation (2026-09-02): build on the server** during the deploy. (Container-registry push/pull remains a possible future optimisation.)
- **Deploy path** — **DECIDED (2026-09-13):** the server checkout is disposable and every deploy asserts the commit it shipped (see §5, threat-model T11). Taken after a force-push to `main` left production serving five-day-old code while every deploy, and the Actions run, reported success.

## 8. Known follow-ups

- **Dependabot** reports 1 high + 1 moderate vulnerability on `main` (as of 2026-09-02) — to be triaged in the repo Security tab.
- **Branch protection / rulesets on `main` are not configured.** The repo currently allows direct pushes and force-pushes — the workflow violation that broke the deploy on 2026-09-08. This one needs the repo owner.
- **Input bounds (threat-model T12):** `backup_arrangements` needs `max_items` and `Destination.address` needs `max_length`, so that one request cannot fan out into an unbounded number of paid upstream calls.
- **The Nginx site config is still not version-controlled** (the repo's `nginx/` holds only a README) and `nginx/**` is not in `deploy.yml`'s `paths:`, so every Nginx change is made by hand on the server — including the SPA `try_files $uri $uri/ /index.html` needed for deep links such as `/map` to survive a hard refresh.
- **CI action versions** need a bump (`actions/checkout@v4`, `actions/setup-python@v5`) — Node 20 deprecation warnings appear in the run log. Do it as its own PR, because `deploy.yml` is inside the deploy `paths:` list and editing it triggers a production deploy.
- **RDS admin password rotation** was deferred during I1 and is now due — see `secret-handling.md`.
- **Deployment checklist** still has open items (T12 input bounds, Dependabot triage); work through them before the next release sign-off.
- Request rate-limiting at the reverse proxy is deferred (noted in `deployment-checklist.md` / `threat-model.md`). HSTS was added on 2026-09-02 (verified via `curl -I`).

## 9. References

- `deployment-checklist.md` — the security gate for every release.
- `secret-handling.md` — how secrets are managed, who owns each key, and how to rotate it.
- `threat-model.md` — T1/T2/T7 inform the auth and external-API decisions above; T11 records the 2026-09-08 deploy incident and its fix.
- `privacy-requirements.md` — what data leaves our infrastructure and to which service.
