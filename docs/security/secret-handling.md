# Secret & Environment Variable Guideline

**Applies to:** all developers on this repo. Read this before adding any API key, database password, or token.

## Rules (non-negotiable)

1. **Never commit secrets.** API keys, database passwords, and tokens go ONLY in environment variables. No secrets in code, config files, or documentation.
2. **`.env` is local-only.** It is already in `.gitignore`. Before every push, check you are not accidentally including it:
   ```bash
   git status
   ```
   If `.env` appears in the list, fix it before pushing.
3. **`.env.example` holds placeholders only** (`change_me`). When you add a new environment variable, update `.env.example` with a placeholder so teammates know what to configure. Never put a real value in `.env.example`.
4. **Set permissions on `.env`:**
   ```bash
   chmod 600 .env
   ```
   This ensures only the owner can read it.
5. **CI/CD secrets go in GitHub Actions Secrets**, not in the repo. Anyone with collaborator access can see workflow definitions — never embed a secret there. (Repo Settings → Security → Secrets and variables.)
6. **Production secrets live in the server's `.env`** (`chmod 600`, never committed) — the accepted arrangement for I1–I2 (see deployment-plan §4). CI credentials live in GitHub Actions Secrets. Moving to AWS Secrets Manager is a planned future improvement; secrets are never baked into images or the repo.
7. **Write secrets into `.env` with an editor, not on a command line.** `sudo nano .env` keeps the value out of shell history and out of the AWS SSM command log, which records every command it runs. The value must be unquoted with no leading or trailing space, or it is read literally, spaces included.

## Key ownership and rotation

Every production secret has a named owner and a way to revoke it. Record a new key here in the same PR that introduces it.

| Key | Provider | Owner | Held in | How to rotate |
| -------------------- | -------------------- | ----------- | --------------- | ---------------------------------- |
| `TOMTOM_API_KEY` | TomTom (Orbis Places, Routing) | deployment lead | server `.env` | Regenerate in the TomTom dashboard → replace the value in the server `.env` → `docker compose up -d --no-deps backend` → revoke the old key |
| `AI_API_KEY` | NVIDIA (`build.nvidia.com`) | deployment lead | server `.env` | Create a new key on the NVIDIA account → replace the value → recreate the container as above → revoke the old key |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | AWS IAM user `github-actions-deploy` | deployment lead | GitHub Actions Secrets | Create a new access key → update the repo secret → confirm the next deploy is green → deactivate the old key |
| `MYSQL_PASSWORD` / `MYSQL_ROOT_PASSWORD` | RDS `fit5120-db` | deployment lead | server `.env`; RDS master credentials | **Deferred during I1 and now due** — see deployment-plan §8 |
| `MIGRATION_DB_PASSWORD` | RDS `fit5120-db` migration user | deployment lead | server `.env` | Create or rotate independently from the Backend user, update the server `.env`, validate the migration service, then retire the old credential |
| Site gate password | Nginx basic auth | deployment lead | `/etc/nginx/.htpasswd` on the server only | `htpasswd` to replace the entry → `nginx -s reload` |

Two rules behind the table:

- **Each key belongs to an individual account, never a shared one.** A shared account cannot be revoked per person, and no one can tell who used it. Where a third party should not receive the key at all, create a **separate production key** on the deployment lead's own account so that it can be rotated and revoked independently.
- **A container restart does not re-read `.env`.** Environment variables are fixed when a container is created, so after editing `.env` the container must be recreated, not restarted: `docker compose up -d --no-deps backend`. A normal deploy does this already, because the image changes.

## Current environment variables

Source of truth: `.env.example` at the repo root. Marked **sensitive** where the value must never be shared or committed.

| Variable | Meaning | Sensitive | Notes |
| -------------------------- | ------------------------------ | --------- | ----------------------------------- |
| `MYSQL_DATABASE` | DB name | no | |
| `MYSQL_USER` | DB user | no | least-privilege app user |
| `MYSQL_PASSWORD` | DB password | **yes** | dev default `change_me` — replace before sharing |
| `MIGRATION_DB_USER` | Dedicated migration DB user | no | required by the disposable migration service only |
| `MIGRATION_DB_PASSWORD` | Dedicated migration DB password | **yes** | required; no default and no fallback to `MYSQL_PASSWORD` |
| `MYSQL_ROOT_PASSWORD` | DB root password | **yes** | replace before sharing |
| `DATABASE_HOST` | DB host | no | `mysql` in Compose; the RDS endpoint in production |
| `DATABASE_PORT` | DB port | no | |
| `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | Connection pool sizing | no | |
| `BACKEND_PORT` | API port | no | |
| `MYSQL_EXPOSED_PORT` | Exposed DB port | no | |
| `APP_*` | Runtime adapters and timeouts (data mode, repository mode, spatial mode, cache age, open-data DB timeouts) | no | |
| `TOMTOM_API_KEY` | TomTom address lookup and routing key | **yes** | required when `APP_DATA_MODE=live`; the app refuses to start live without it |
| `AI_API_KEY` | NVIDIA hosted-model key for the rendezvous explanation | **yes** | optional; with no key the feature is disabled and the rest of the app runs normally |

**When you add a future key**, add it to `.env.example` with a placeholder in the same commit, and add a row to the ownership table above.

## Pitfalls from our earlier project

- The `.env` was once placed at the repo root with default permissions, exposing DB credentials to any local user. Always keep `chmod 600 .env`.
- Environment variables were referenced from the wrong path (`backend/` vs repo root). Keep a single `.env` at the repo root and document the expected path in the README.
- A rotating `cp .env .env.bak` backup leaves a second plaintext copy of every secret on the server. Delete it as soon as the edit is verified.
