# Deployment Plan (I1)

**Project:** Shielding Crisis & Community Resilience — I1.
**Owner:** Cybersecurity & Deployment Lead. **Status:** draft v0.1 — framework; provisioning happens once the I1 code is runnable. Items marked ⏳ are pending infrastructure.

## 1. Target architecture

Single EC2 instance running the existing Docker Compose stack, fronted by Nginx with HTTPS. Matches the layout already described in `nginx/README.md`.

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
- **Nginx** terminates HTTPS and routes `/api` to FastAPI; frontend is served as static files.

## 2. Components

- **EC2** — Ubuntu 24.04, t3.micro (⏳ provision when code is runnable). Access via **AWS SSM Session Manager** (no SSH/port 22), as hardened in our earlier project.
- **Backend** — `backend/Dockerfile` already exists (python:3.12-slim, uvicorn :8000). No change needed.
- **MySQL / RDS** — **DECIDED: reuse the existing `fit5120-db` RDS (db.t4g.micro, MySQL 8.4).** The `mysql:8.4` service in `docker-compose.yml` stays for local dev only; production points `DATABASE_HOST` at the RDS endpoint. On deploy day: take a safety snapshot → drop the old project's schema → apply `database/init/001_initial_schema.sql` manually (RDS does not auto-run init scripts).
- **Frontend** — Vue build output copied to the server (or served by Nginx container). ⏳ frontend not initialized yet.
- **Nginx** — config lives in `nginx/` (currently README only). ⏳ write production config when routing is known. Includes a **shared-password basic auth gate** covering `/` and `/api`, so only the team and teaching staff can view the site (see §7).
- **HTTPS** — Let's Encrypt via certbot, auto-renewal cron. Domain: **`cubesix.me` (temporary)** — reusing the earlier project's domain; swap later if the team prefers a new one.

## 3. Networking & security groups

- Inbound: **80 + 443 from 0.0.0.0/0** only.
- **No port 22** — use SSM Session Manager (SSM role `AmazonSSMManagedInstanceCore`).
- **MySQL port not exposed** — RDS has public access off; reachable only from the EC2 security group.
- Outbound: needed for apt updates, image pulls, and the external APIs (Vicmap / CFA / BOM).

## 4. Secret flow

- **Local dev** — `.env` at repo root (`chmod 600`), gitignored
- **CI/CD** — GitHub Actions Secrets (never in workflow files)
- **Production** — `.env` on the server, or **AWS Secrets Manager** for the long term
- **Site gate password** — Nginx basic auth credential (htpasswd) stored on the server only, never committed to the repo

Source of truth for variable names: `.env.example` (see `secret-handling.md`).

## 5. CI/CD path

Current `deploy.yml` is a **manual, non-deploying scaffold**. Target pipeline (once infra exists):

1. Merge to `main` → CI runs tests + dependency scan (already partly in `backend-ci.yml`).
2. Deployment workflow (⏳ to build): authenticate to EC2 via SSM/SSH with stored secrets → pull code → `docker compose up -d --build` → health-check `/api/health`.

Deploy secrets (SSH key / SSM role ARN) are added to GitHub Actions Secrets at that point — never in the workflow files.

## 6. Deployment runbook (executed at deploy time)

1. ⏳ Provision EC2 (Ubuntu 24.04, t3.micro), attach SSM role, set security groups (80/443 only).
2. ⏳ Register DNS: point domain → EC2 IP.
3. Install Docker + Docker Compose plugin on the server.
4. Copy `.env` (real values, including `DATABASE_HOST` = RDS endpoint) to repo root on server; `chmod 600`.
5. Prepare RDS: take a safety snapshot → drop the old project's schema → apply `database/init/001_initial_schema.sql` (see §2).
6. `docker compose up -d --build` (production override: no `mysql` service); verify `curl -I https://<domain>/api/health`.
7. Set up Nginx reverse proxy (`/` → frontend, `/api` → backend:8000, basic auth gate) + certbot HTTPS + auto-renew.
8. Run the security checks in `deployment-checklist.md`; archive evidence.

## 7. Open decisions (need team input)

- **Domain** — **DECIDED (temporary): `cubesix.me`.** Reusing the earlier project's domain. Easy to change later (DNS + certbot, ~10 min) if the team prefers a new domain.
- **Auth model** — **DECIDED (2026-08-31): shared-password site gate.** Nginx basic auth on `/` and `/api` with a shared password, so only the team and teaching staff can view the app. No per-user login for I1 (see `threat-model.md` T1/T2). The gate password is a deployment secret (§4).
- **Database** — **DECIDED (2026-09-01): reuse the existing `fit5120-db` RDS.** Old project data is removed on deploy day (after a safety snapshot); Docker MySQL stays for local dev only (see §2).
- **Images** — build on the server, or push to GitHub Container Registry and pull?

## 8. References

- `deployment-checklist.md` — the security gate for every release.
- `secret-handling.md` — how secrets are managed.
- `threat-model.md` — T1/T2/T7 inform the auth and external-API decisions above.
