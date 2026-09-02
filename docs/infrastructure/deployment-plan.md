# Deployment Plan (I1)

**Project:** Shielding Crisis & Community Resilience — I1.
**Owner:** Cybersecurity & Deployment Lead. **Status: IMPLEMENTED — live since 2026-09-02** (https://cubesix.me). This document describes the deployed system and the CI/CD path that keeps it updated.

## 1. Architecture (live)

One EC2 instance runs the backend as a Docker container; Nginx serves the static frontend, terminates HTTPS, and proxies `/api` to the backend. Matches the layout described in `nginx/README.md`.

```
                     Internet
                        │  HTTPS 80/443
                        v
                     Nginx (reverse proxy + basic auth gate)
                        │
            ┌───────────┴────────────┐
            │  /  → frontend (Vue)   │  /api → backend:8000
            v                         v
        frontend static            Backend (FastAPI, container)
                                        │
                                        v
                             RDS (MySQL 8.4, managed, SG-locked to EC2)
```

Key points:
- **One EC2** keeps cost and ops simple for a student prototype (same pattern as our earlier project).
- **Database = AWS RDS (MySQL 8.4)** — managed service, never exposed publicly; the RDS security group allows MySQL from the EC2 only.
- **Nginx** terminates HTTPS and routes `/api` to FastAPI; frontend is served as static files from `/var/www/html`.
- **Auto-deploy** (see §5): merging to `main` triggers tests + a remote deploy over AWS SSM — no manual server steps for a normal release.

## 2. Components

- **EC2** — Ubuntu 24.04, t3.micro, `i-060c00865b0bf629e` (ap-southeast-4, public `16.50.155.51`). **Access via AWS SSM Session Manager only** (no port 22). Boot volume is 20 GiB gp3 (resized from 8 GiB on 2026-09-02 — the 8 GiB disk repeatedly filled up during builds; see §6 ops notes).
- **Backend** — `backend/Dockerfile` (python:3.12-slim, uvicorn :8000), run as a container via Docker Compose; health check at `/api/health`.
- **MySQL / RDS** — **reusing the existing `fit5120-db` (db.t4g.micro, MySQL 8.4).** Production `DATABASE_HOST` points at the RDS endpoint; the `mysql:8.4` service in `docker-compose.yml` is local dev only. Schema was applied manually on deploy (RDS does not auto-run init scripts).
- **Frontend** — Vue 3 + Vite. Production build (`npm run build`) output is copied to `/var/www/html/`.
- **Nginx** — production config at `/etc/nginx/sites-enabled/default`: `server_name cubesix.me www.cubesix.me`, `location /` → static frontend, `location /api/` → proxy to `127.0.0.1:8000`, **shared-password basic auth gate** covering `/` and `/api` (see §7 auth).
- **HTTPS** — Let's Encrypt via certbot on `cubesix.me` (temporary domain; auto-renewal active).

## 3. Networking & security groups

- Inbound: **80 + 443 from 0.0.0.0/0** only.
- **No port 22** — management is via SSM Session Manager (instance role `EC2-SSM-Role`, policy `AmazonSSMManagedInstanceCore`).
- **MySQL not exposed** — RDS has public access off; reachable only from the EC2 security group.
- Outbound: apt updates, image pulls, external APIs (Vicmap / CFA / BOM).

## 4. Secret flow

- **Local dev** — `.env` at repo root (`chmod 600`), gitignored.
- **CI/CD** — GitHub Actions Secrets (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`) — never in workflow files.
- **Production** — `.env` on the server at the repo root; **server pulls the repo via an SSH deploy key** (`/root/.ssh/github_deploy`, read-only, added in the repo's Deploy Keys).
- **Site gate password** — Nginx basic-auth htpasswd file on the server only, never committed.
- **Deploy IAM** — IAM user `github-actions-deploy` (no console) with a scoped inline policy allowing only SSM `SendCommand`/invocation reads on the instance (plus `ec2:DescribeInstances`); used only by GitHub Actions.

Source of truth for variable names: `.env.example` (see `secret-handling.md`).

## 5. CI/CD path (live)

`.github/workflows/deploy.yml` runs on push/merge to `main` (paths: `backend/**`, `frontend/**`, `data/**`, `scripts/**`, `docker-compose.yml`, the workflow itself) and on `workflow_dispatch`.

```
Merge to main
   → Job 1: backend tests (pytest)          — if they fail, the deploy job never runs
   → Job 2: deploy to EC2 via AWS SSM
        1. send-command starts scripts/deploy.sh on the server, DETACHED
           (setsid; stdout → /var/log/fit5120-deploy.log)
        2. workflow awaits that kickoff command's own Status (send-command is
           async — polling its side-effects too early caused a false "NO_LOG")
        3. workflow polls /var/log/fit5120-deploy.status → "0" = success
        4. tails the log into the Actions run
```

`scripts/deploy.sh` (server-side) does: `git pull` → `docker compose up -d --build --no-deps backend` → `docker system prune -f` (disk hygiene) → frontend `npm ci` + `npm run build` → copy `dist` to `/var/www/html/` → health-check `curl /api/health`.

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
8. **In progress:** security checks in `deployment-checklist.md` are being worked through; evidence goes in `docs/security/evidence/`.

**Ops notes learned during bring-up (worth keeping):**

- **SSM runs commands as root with no `HOME`** → the kickoff `export HOME=/root` and `git config --global --add safe.directory <repo>` before `git pull` (root operating on an ubuntu-owned repo would otherwise be a "dubious ownership" fatal).
- **Disk is the scarce resource.** The 8 GiB boot volume filled to 100% mid-deploy (killed a frontend copy with `ENOSPC`). Fixed by resizing to 20 GiB (console Modify volume → `growpart /dev/nvme0n1 1` → `resize2fs /dev/nvme0n1p1`) plus `docker system prune -f` after each build in `deploy.sh`. If disk creeps up again: `sudo df -h /`, `sudo du -xh --max-depth=1 / 2>/dev/null | sort -rh | head`, `sudo apt-get autoremove --purge -y`, `sudo journalctl --vacuum-size=20M`.
- **Deploy log / status** live on the server at `/var/log/fit5120-deploy.log` and `/var/log/fit5120-deploy.status` — the GitHub Actions "tail the log" step prints the end of the former into the run output.

## 7. Decisions (recorded)

- **Domain** — **DECIDED (temporary): `cubesix.me`** (reused from the earlier project). Swappable later via DNS + certbot (~10 min).
- **Auth model** — **DECIDED (2026-08-31): shared-password site gate.** Nginx basic auth on `/` and `/api` with one shared password; no per-user login for I1 (see `threat-model.md` T1/T2).
- **Database** — **DECIDED (2026-09-01): reuse `fit5120-db` RDS.** Old project data removed after a safety snapshot; Docker MySQL stays local-dev-only.
- **Images** — **DECIDED by implementation (2026-09-02): build on the server** during the deploy. (Container-registry push/pull remains a possible future optimisation.)

## 8. Known follow-ups

- **Dependabot** reports 1 high + 1 moderate vulnerability on `main` (as of 2026-09-02) — to be triaged in the repo Security tab.
- **deployment-checklist.md** items still unchecked are the remaining security gate; work through before the I1 release sign-off.
- HSTS header and request rate-limiting at the reverse proxy are deferred (noted in `deployment-checklist.md` / `threat-model.md`).

## 9. References

- `deployment-checklist.md` — the security gate for every release.
- `secret-handling.md` — how secrets are managed.
- `threat-model.md` — T1/T2/T7 inform the auth and external-API decisions above.
