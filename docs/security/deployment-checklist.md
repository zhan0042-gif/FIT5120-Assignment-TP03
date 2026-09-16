# Pre-Deployment Security Checklist

**Purpose:** the security gate before any release. Work through every item, then sign off in the "Final sign-off" section.

> Status as of **2026-09-14**: deployment is live (https://cubesix.me). `[x]` = verified done (evidence in parentheses); items left unchecked are either pending verification or deliberately deferred — reasons are noted inline next to the item.

## 1. Transport security

- [x] HTTPS is enforced for all traffic (HTTP→HTTPS redirect on the reverse proxy) — nginx :80 block returns 301 to https://cubesix.me
- [x] TLS certificate issued and auto-renewal configured (e.g. Let's Encrypt) — certbot-managed on cubesix.me
- [x] HSTS header set — `Strict-Transport-Security: max-age=31536000` added to the 443 server block with `always` (2026-09-02), verified via `curl -I`
- [x] IP-direct access does not bypass HTTPS (redirects to the domain) — port 80 301s regardless of Host header

## 2. Access control

- [x] **Auth model (DECIDED):** shared-password site gate — Nginx basic auth on `/` and `/api` — implemented; no per-user login (see threat-model T1/T2)
- [x] Default passwords changed; credentials not shared in chat or repo — site gate password lives only in `/etc/nginx/.htpasswd` on the server
- [x] Database uses a **non-root** app account — app connects as `fit5120_app` (**note:** currently `ALL PRIVILEGES`, over-privileged — F8 in the vulnerability assessment report; least-privilege grants planned, R6)

## 3. Secrets

- [x] No secrets in the repo, images, or frontend build (see secret-handling) — repo scanned; frontend bundle contains no credentials (auth is nginx-level)
- [x] `.env` not present on the server in world-readable form (`chmod 600`)
- [x] Production secrets in AWS Secrets Manager (or equivalent), not hard-coded — **not used**: `.env` on the server remains the accepted arrangement (see deployment-plan §4); revisit if the project outlives the course
- [x] GitHub Actions secrets set, not written in workflow files — `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` stored as repo secrets
- [x] Every production key present on the server and **owned** — `TOMTOM_API_KEY` and `AI_API_KEY` are set in the server `.env` and recorded with an owner and a rotation path in `secret-handling.md`. Verify presence without printing the value: `docker compose exec -T backend printenv AI_API_KEY | wc -c` (prints a length, never the key)
- [ ] Dedicated migration credentials configured — `MIGRATION_DB_USER` and `MIGRATION_DB_PASSWORD` belong only to the disposable migration service; Backend continues to receive only `MYSQL_USER` and `MYSQL_PASSWORD`
- [x] Secrets written with an editor, never as a command-line argument — an SSM `send-command` command string is recorded in full, so the value must go in through `sudo nano`, not `export` or an inline argument

## 4. API / application config

- [x] `debug = false` / no stack traces in production error responses (threat-model T8) — uvicorn started without `--reload`/debug; all exceptions translated to sanitized `{"detail": ...}` JSON in `backend/app/main.py`
- [x] CORS restricted to the actual frontend origin(s) — CORS middleware is **not enabled** → same-origin only (cross-origin blocked); frontend and `/api` are served same-origin by Nginx
- [x] Input length/type validation on all endpoints; error messages sanitized — pydantic request schemas validate input; custom exception handlers emit sanitized messages
- [x] External API calls (TomTom Orbis / TomTom Routing / CFA / BOM) have timeouts and graceful failure (T7) — TomTom autocomplete/reverse lookup use a 4s deadline and geocoding uses a 10s deadline; BOM uses 15s and CFA 10s; failures map to 503 via `ExternalDataUnavailable`
- [ ] Every input that fans out into paid upstream calls is bounded (T12) — **open**: `backup_arrangements` has no `max_items` and `Destination.address` has no `max_length`, so one plan-save request can drive an unbounded number of TomTom verification calls
- [x] Optional third-party features fail closed, not open (T13) — the AI explanation has no key path that raises at import: a missing or blank `AI_API_KEY` selects a disabled client, so the app starts normally and only that button produces nothing
- [x] Every outbound service appears in `privacy-requirements.md` §5 with the data it receives — TomTom Places, TomTom Routing, CFA, BOM, BPA open data, NVIDIA

## 5. Security headers / reverse proxy

- [x] Reverse proxy config reviewed before it is used in production — config reviewed and `nginx -t` passed before reload
- [x] Security Groups / firewall: only 80/443 exposed; management via SSM Session Manager (**no port 22**) — backend container port tightened to `127.0.0.1:8000` (2026-09-02) so it is not reachable on the public interface even if a group rule is later widened

## 6. Data

- [x] No addresses / coordinates / support needs in backend logs (privacy-requirements §3) — verified: backend app code performs no logging of requests or addresses; running container logs spot-checked clean (2026-09-02)
- [x] Browser geolocation requested only on an explicit user gesture, never on load (privacy-requirements §6) — the button in the local-context card is the only caller of `navigator.geolocation.getCurrentPosition`
- [x] **Schema changes applied to production before the code that needs them** — RDS does not run `database/init/`; migrations 009+ and dependent one-time data jobs are tracked and applied automatically before Backend activation. Migrations through 008 remain the manually applied legacy baseline.
- [ ] **Automatic migration preflight completed** — confirm RDS matches legacy 001–008, provision the dedicated least-privilege migration user, configure its two protected environment variables, and verify the migration container can connect before merging the automation PR
- [x] **Team migration rule documented** — every production schema change, including an existing-table change, is a new numbered migration; applied files are immutable; the runner uses files/history rather than schema diffing; manual production DDL is reserved for emergency operator remediation
- [x] RDS automated backups configured — **Enabled**, 1-day retention. Note: this account is on the AWS Free Tier, which caps RDS backup retention at 1 day; 7-day retention would require a paid plan — accepted for a student project
- [x] RDS deletion protection enabled — **Enabled** (2026-09-02, RDS Modify)
- [x] Encryption at rest enabled on RDS — **Enabled** (AWS managed KMS key `aws/rds`)
- [x] RDS security group allows MySQL from the EC2 only (public access off)
- [x] No real personal data in seed/mock data — mock providers + seed data are synthetic

## 7. Build / CI

- [x] Backend CI runs tests — `deploy.yml` runs `pytest` on every push to `main` before deploying (a failing test blocks the deploy)
- [x] Frontend build contains no secrets — no credentials in built assets (auth is at the Nginx gate, not in the bundle); repo secret scan clean (2026-09-02: no tracked `.env`/keys, `.gitignore` excludes `.env`, no hard-coded secrets in source)
- [x] The deploy cannot report success while shipping stale code (T11) — the server checkout is disposable (`git fetch --prune` + `git reset --hard origin/main`, never `git pull --ff-only`), the deploy body runs in a subshell so `set -e` applies, the kickoff command runs under `set -e`, the deployed SHA is logged, and the script asserts `HEAD == origin/main` before writing a success status
- [x] The deployed commit can be identified after the fact — `/var/log/fit5120-deploy.log` records `=== Deploying commit <sha>: <subject> ===` and `=== Deploy OK: <sha> ===`; verify with `grep -n -E "Deploying commit|Deploy OK|FAILED|fatal" /var/log/fit5120-deploy.log`
- [x] A successful HTTP response is never treated as proof of a deploy — a live `/api/health` 200 says nothing about *which* code is serving it. Confirm with `git log --oneline -1` on the server and a file-level check (`docker exec fit5120-assignment-tp03-backend-1 ls app/providers/`)
- [ ] Dependency scan clean or documented exceptions (see dependency-scan) — **open**: Dependabot reports 1 high + 1 moderate on `main` (as of 2026-09-02) — to triage

## 8. Monitoring (student-project level)

- [x] Basic access/error logs reachable on the server — Nginx access/error logs; deploy log at `/var/log/fit5120-deploy.log`
- [ ] (Optional) CloudWatch / CloudTrail / GuardDuty enabled for the AWS account — **not enabled** (optional at student-project level)
- [ ] An in-progress deploy is distinguishable from one that never started — **open**: the status file is deleted at the start of a run and only written at the end, so a missing file means either "running" or "never started". Until this is changed, read the log tail rather than the status file alone

## 9. Final sign-off

- [ ] Every relevant item above checked
- [ ] Evidence submitted in PGP (Security folder) — vulnerability assessment report + screenshots
- [ ] Signed off by: ____________  Date: ____________
