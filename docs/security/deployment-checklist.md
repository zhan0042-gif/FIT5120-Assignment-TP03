# Pre-Deployment Security Checklist

**Purpose:** the security gate before any release. Work through every item, then sign off in the "Final sign-off" section.

> Status as of **2026-10-12**: deployment is live (https://cubesix.me), with the completed Iteration 1 and Iteration 2 builds archived at https://cubesix.me/i1/ and https://cubesix.me/i2/. `[x]` = verified done (evidence in parentheses); items left unchecked are either pending verification or deliberately deferred — reasons are noted inline next to the item.

## 1. Transport security

- [x] HTTPS is enforced for all traffic (HTTP→HTTPS redirect on the reverse proxy) — nginx :80 block returns 301 to https://cubesix.me
- [x] TLS certificate issued and auto-renewal configured (e.g. Let's Encrypt) — certbot-managed on cubesix.me
- [x] HSTS header set — `Strict-Transport-Security: max-age=31536000` added to the 443 server block with `always` (2026-09-02), verified via `curl -I`
- [x] IP-direct access does not bypass HTTPS (redirects to the domain) — port 80 301s regardless of Host header

## 2. Access control

- [x] **Auth model (DECIDED):** shared-password site gate — Nginx basic auth on `/` and `/api` — implemented; no per-user login (see threat-model T1/T2). The gate is declared at **server** level, so the archive locations `/i1/` and `/i2/` inherit it without repeating the directive (see threat-model T21)
- [x] Default passwords changed; credentials not shared in chat or repo — site gate password lives only in `/etc/nginx/.htpasswd` on the server
- [x] Database uses a **non-root** app account — app connects as `fit5120_app` (**note:** currently `ALL PRIVILEGES`, over-privileged — F8 in the vulnerability assessment report; least-privilege grants planned, R6)

## 3. Secrets

- [x] No secrets in the repo, images, or frontend build (see secret-handling) — repo scanned; frontend bundle contains no credentials (auth is nginx-level)
- [x] `.env` not present on the server in world-readable form (`chmod 600`)
- [x] Production secrets in AWS Secrets Manager (or equivalent), not hard-coded — **not used**: `.env` on the server remains the accepted arrangement (see deployment-plan §4); revisit if the project outlives the course
- [x] GitHub Actions secrets set, not written in workflow files — `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` stored as repo secrets
- [x] Every production key present on the server and **owned** — `TOMTOM_API_KEY`, `AI_API_KEY`, `OPENAI_API_KEY` and `VIC_ROAD_DISRUPTIONS_API_KEY` are set in the server `.env` and recorded with an owner and a rotation path in `secret-handling.md`. Verify presence without printing the value: `docker compose exec -T backend printenv AI_API_KEY | wc -c` (prints a length, never the key). Note the same trap in reverse: a **blank** key selects a disabled client rather than raising, so a present-but-empty variable passes a presence check while silently disabling the feature. Verified 2026-10-12: all four present and non-empty in the running backend container
- [x] Dedicated migration credentials configured — `MIGRATION_DB_USER` and `MIGRATION_DB_PASSWORD` belong only to the disposable migration service; Backend continues to receive only `MYSQL_USER` and `MYSQL_PASSWORD`. Verified 2026-10-12: `docker-compose.yml` declares both variables on the `migration` service only (the `backend` service block does not carry them), and the deploy log records `Required migration database credentials are configured.` running inside that container
- [x] Secrets written with an editor, never as a command-line argument — an SSM `send-command` command string is recorded in full, so the value must go in through `sudo nano`, not `export` or an inline argument

## 4. API / application config

- [x] `debug = false` / no stack traces in production error responses (threat-model T8) — uvicorn started without `--reload`/debug; all exceptions translated to sanitized `{"detail": ...}` JSON in `backend/app/main.py`
- [x] CORS restricted to the actual frontend origin(s) — CORS middleware is **not enabled** → same-origin only (cross-origin blocked); frontend and `/api` are served same-origin by Nginx
- [x] Input length/type validation on all endpoints; error messages sanitized — pydantic request schemas validate input; custom exception handlers emit sanitized messages
- [x] External API calls (TomTom Orbis / TomTom Routing / CFA / BOM / road disruption feed) have timeouts and graceful failure (T7) — TomTom autocomplete/reverse lookup use a 4s deadline and geocoding uses a 10s deadline; BOM uses 15s, CFA 10s, and the road disruption client 8s; failures map to 503 via `ExternalDataUnavailable`, except the road disruption feed, whose failure surfaces as the "information unavailable" state instead (T19)
- [ ] Every input that fans out into paid upstream calls is bounded (T12) — **open**: `backup_arrangements` has no `max_items` and `Destination.address` has no `max_length`, so one plan-save request can drive an unbounded number of TomTom verification calls
- [x] Optional third-party features fail closed, not open (T13) — the AI explanation has no key path that raises at import: a missing or blank `AI_API_KEY` selects a disabled client, so the app starts normally and only that button produces nothing. The voice feature behaves the same way: with a blank `OPENAI_API_KEY`, `_live_session_client` and `_action_decision_client` in `backend/app/core/config.py` return disabled clients, so the app starts normally and the voice feature simply produces nothing (verified 2026-10-12)
- [ ] **Every endpoint that spends the shared hosted quota is rate-limited** — **open**: the two model-backed endpoints draw on one `AI_API_KEY` and therefore one account quota, but only `/safety-guidance/ask` carries a limit (`AskRateLimit`, 6 per household / 30 overall per 60 s). `/rendezvous-explanation` has none — eight sequential calls all reached the model (penetration test report, Test 11; threat-model T10)
- [x] Every outbound service appears in `privacy-requirements.md` §5 with the data it receives — TomTom Places, TomTom Routing, CFA, BOM, BPA open data, NVIDIA, OpenAI (voice: the session handshake, the action chooser, and the live audio the browser sends directly — T23), and the Victorian road disruption feed. The last of these is the one boundary that receives **nothing about the household and nothing about the person using it** — no address, no coordinates, no identifier, and not even the device's transport details: the request carries pagination and the key only, and the destination coordinates are used locally to filter the response (T18). Verified in `backend/app/providers/road_disruptions.py` `_fetch_all()` on 2026-10-06

## 5. Security headers / reverse proxy

- [x] Reverse proxy config reviewed before it is used in production — config reviewed and `nginx -t` passed before reload
- [x] Security Groups / firewall reviewed — 80/443 are the only ports open to `0.0.0.0/0`; **port 22 is open but restricted to the operator's home IP** (`101.188.108.19/32`) as the emergency fallback for when SSM Session Manager is unavailable (accepted operational risk — F5/R5 in the vulnerability assessment report). Management is normally via SSM. The backend container port is bound to `127.0.0.1:8000` (2026-09-02) so it is not reachable on the public interface even if a group rule is later widened. **The same is not true of the database container.** `docker-compose.yml` publishes `mysql` as `"${MYSQL_EXPOSED_PORT:-3306}:3306"`, and nothing sets that variable on the server, so the container binds `0.0.0.0:3306` and `[::]:3306` (verified 2026-10-15 with `ss -ltnp`: both sockets are held by `docker-proxy`). Production does not use this container — the backend's `DATABASE_HOST` resolves to the RDS endpoint — so no production data is exposed, but the port is open on every interface and the security group is the only thing closing it. `deployment-plan.md` §3 describes the `mysql` service as local-dev only; on the deployed host it runs, because `docker compose up -d` starts every service in the file and `backend` declares `depends_on: mysql: service_healthy`. **Fix:** bind it to `127.0.0.1:3306` or gate the service behind a Compose profile so it does not start in production
- [x] Archived iteration builds are behind the gate — `/i1/` and `/i2/` are static directories under `/var/www/html` served by `location` blocks in `/etc/nginx/sites-enabled/default`. `auth_basic` and `auth_basic_user_file` are set at **server** level and location blocks inherit server-level directives, so both archive paths carry the gate without repeating it (T21). Each block has its own `try_files $uri $uri/ /iN/index.html`, so a deep link such as `/i1/plan` resolves inside the archive instead of falling through to the main site's `index.html`
- [x] Unauthenticated request to each archive path returns 401 — **verified 2026-10-07**: `curl -s -o /dev/null -w '%{http_code}'` against `https://cubesix.me/`, `https://cubesix.me/i1/` and `https://cubesix.me/i2/` returned `401`, `401` and `401` with no credentials supplied. The gate is inherited from the server-level configuration as recorded in the item above (T21); the penetration test report's Test 2 asserts the gate for all traffic but does not name either archive path, so the per-path probe is recorded here

## 6. Data

- [x] No addresses / coordinates / support needs in backend logs (privacy-requirements §3) — verified: backend app code performs no logging of requests or addresses; running container logs spot-checked clean (2026-09-02)
- [x] Browser geolocation requested only on an explicit user gesture, never on load (privacy-requirements §6) — the button in the local-context card is the only caller of `navigator.geolocation.getCurrentPosition`
- [x] **Schema changes applied to production before the code that needs them** — RDS does not run `database/init/`; migrations 009+ and dependent one-time data jobs are tracked and applied automatically before Backend activation. Migrations through 008 remain the manually applied legacy baseline.
- [x] **Automatic migration preflight completed** — confirm RDS matches legacy 001–008, provision the dedicated least-privilege migration user, configure its two protected environment variables, and verify the migration container can connect before merging the automation PR. **Verified 2026-10-12:** the deploy log for `9598f50` records `Required migration database credentials are configured.` followed by `Schema migration already applied: 009_add_fire_history_area_ha.sql` / `010_fdr_history.sql` and `No pending schema migrations.` The "already applied" lines can only be produced by reading the migration history table over a live connection, so the container connecting is proven rather than assumed
- [x] **Migration grants reviewed** — the separate deployment account may require `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`, `INDEX`, and `REFERENCES`, but grant only those used by reviewed migration SQL; these are not Backend runtime privileges. **Verified 2026-10-12:** `SHOW GRANTS` reports ``SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, REFERENCES, INDEX, DROP ON `fit5120`.*`` plus the implicit `USAGE ON *.*`, which grants nothing. Scoped to the application database only — no `ALL PRIVILEGES`, no `GRANT OPTION`, no admin privileges, and the credential is never passed to the Backend container. All except `DROP` and `INDEX` are exercised by the applied migrations (002, 003 and 005 use `UPDATE`; four `CREATE TABLE` statements use `REFERENCES`); those two are retained so that a future forward-only migration can drop a column or add an index without a manual `GRANT`
- [x] **Migration remains compatible with the running Backend** — default to additive changes; destructive changes use expand/migrate/contract across deployments, remain small and forward-only, and include an operator plan because MySQL DDL may not roll back after a partial failure. **Verified 2026-10-12:** both applied migrations are purely additive — 009 is `ALTER TABLE open_data_fire_history ADD COLUMN area_ha DECIMAL(18,6) NULL`, 010 is `CREATE TABLE open_data_fdr_history`. Neither drops nor rewrites existing data, so the Backend running at the time remained valid against the new schema
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
- [ ] Dependency scan clean or documented exceptions (see dependency-scan) — **open**: Dependabot reports 1 critical and 1 high on `main` (verified 2026-10-12), both in `frontend/package-lock.json`, but they do not share a reachability story. `maplibre-gl` (sanitizer bypass in `DOM.sanitize()`, installed 5.24.0, patched in 6.4.1) is a runtime dependency: it is bundled and does ship to visitors, and the fix is a major-version upgrade. `source-map-js` (event-loop denial of service, installed 1.2.1, patched in 1.2.2) is build-time only — it arrives through `@vue/compiler-sfc` and `postcss`, is imported by no runtime code, and never enters the browser bundle, so its denial of service lands on the build machine and on CI rather than on a visitor. Disposition: documented exception — reachability assessment in `dependency-scan.md`

## 8. Monitoring (student-project level)

- [x] Basic access/error logs reachable on the server — Nginx access/error logs; deploy log at `/var/log/fit5120-deploy.log`
- [ ] (Optional) CloudWatch / CloudTrail / GuardDuty enabled for the AWS account — **not enabled** (optional at student-project level)
- [ ] An in-progress deploy is distinguishable from one that never started — **open**: the status file is deleted at the start of a run and only written at the end, so a missing file means either "running" or "never started". Until this is changed, read the log tail rather than the status file alone

## 9. Final sign-off

- [ ] Every relevant item above checked
- [ ] Evidence submitted in PGP (Security folder) — vulnerability assessment report + screenshots
- [ ] Signed off by: ____________  Date: ____________
