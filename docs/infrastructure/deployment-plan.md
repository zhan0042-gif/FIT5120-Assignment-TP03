# Deployment Plan (I1)

**Project:** Shielding Crisis & Community Resilience — I1.
**Owner:** Cybersecurity & Deployment Lead. **Status:** draft v0.1 — framework; provisioning happens once the I1 code is runnable. Items marked ⏳ are pending infrastructure.

## 1. Target architecture

Single EC2 instance running the existing Docker Compose stack, fronted by Nginx with HTTPS. Matches the layout already described in `nginx/README.md`.

```
                     Internet
                        │  HTTPS 80/443
                        v
                     Nginx (reverse proxy)
                        │
            ┌───────────┴────────────┐
            │  /  → frontend (Vue)   │  /api → backend:8000
            v                         v
        frontend static            Backend (FastAPI, container)
                                        │
                                        v
                                   MySQL (container, internal network only)
```

Key points:
- **One EC2** keeps cost and ops simple for a student prototype (same pattern as our earlier project).
- **MySQL stays inside the Docker network** — never exposed publicly in production.
- **Nginx** terminates HTTPS and routes `/api` to FastAPI; frontend is served as static files.

## 2. Components

- **EC2** — Ubuntu 24.04, t3.micro (⏳ provision when code is runnable). Access via **AWS SSM Session Manager** (no SSH/port 22), as hardened in our earlier project.
- **Backend** — `backend/Dockerfile` already exists (python:3.12-slim, uvicorn :8000). No change needed.
- **MySQL** — `mysql:8.4` service already in `docker-compose.yml`, named volume `mysql_data`. ⏳ Remove `MYSQL_EXPOSED_PORT` for production so the DB is internal only.
- **Frontend** — Vue build output copied to the server (or served by Nginx container). ⏳ frontend not initialized yet.
- **Nginx** — config lives in `nginx/` (currently README only). ⏳ write production config when routing is known.
- **HTTPS** — Let's Encrypt via certbot, auto-renewal cron. Domain: **`cubesix.me` (temporary)** — reusing the earlier project's domain; swap later if the team prefers a new one.

## 3. Networking & security groups

- Inbound: **80 + 443 from 0.0.0.0/0** only.
- **No port 22** — use SSM Session Manager (SSM role `AmazonSSMManagedInstanceCore`).
- **MySQL port not exposed** on the host in production.
- Outbound: needed for apt updates, image pulls, and the external APIs (Vicmap / CFA / BOM).

## 4. Secret flow

| Environment | Where secrets live |
|---|---|
| Local dev | `.env` at repo root (`chmod 600`), gitignored |
| CI/CD | GitHub Actions Secrets (never in workflow files) |
| Production | `.env` on the server, or **AWS Secrets Manager** for the long term |

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
4. Copy `.env` (real values) to repo root on server; `chmod 600`.
5. `docker compose up -d --build`; verify `curl -I https://<domain>/api/health`.
6. Set up Nginx reverse proxy (`/` → frontend, `/api` → backend:8000) + certbot HTTPS + auto-renew.
7. Run the security checks in `deployment-checklist.md`; archive evidence.

## 7. Open decisions (need team input)

- **Domain** — **DECIDED (temporary): `cubesix.me`.** Reusing the earlier project's domain. Easy to change later (DNS + certbot, ~10 min) if the team prefers a new domain.
- **Auth model** — **DECIDED: no application-level login (no registration/signup).** The I1 prototype uses **Nginx basic auth** as the only gate. Consequence: no per-user authorization in the backend, so the IDOR risk (threat-model T2) is **accepted for the prototype/demo**. Revisit if real multi-user data is introduced.
- **Database** — keep MySQL in Docker, or move to RDS (costs more; safer for sensitive data)?
- **Images** — build on the server, or push to GitHub Container Registry and pull?

## 8. References

- `deployment-checklist.md` — the security gate for every release.
- `secret-handling.md` — how secrets are managed.
- `threat-model.md` — T1/T2/T7 inform the auth and external-API decisions above.
