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
6. **Production secrets live in the server's `.env`** (`chmod 600`, never committed) — the accepted arrangement for I1 (see deployment-plan §4). CI credentials live in GitHub Actions Secrets. Moving to AWS Secrets Manager is a planned I2 improvement; secrets are never baked into images or the repo.

## Current environment variables

Source of truth: `.env.example` at the repo root. Marked **sensitive** where the value must never be shared or committed.

- `MYSQL_DATABASE` — DB name — not sensitive
- `MYSQL_USER` — DB user — not sensitive — least-privilege app user
- `MYSQL_PASSWORD` — DB password — **sensitive** — dev default `change_me`, replace before sharing
- `MYSQL_ROOT_PASSWORD` — DB root password — **sensitive** — replace before sharing
- `DATABASE_HOST` — DB host (`mysql` in Compose) — not sensitive
- `DATABASE_PORT` — DB port — not sensitive
- `BACKEND_PORT` — API port — not sensitive
- `MYSQL_EXPOSED_PORT` — exposed DB port — not sensitive
- `AI_API_KEY` — AI provider key — **sensitive** — leave empty until provider chosen

**When you add a future key** (e.g. a CFA/BOM or ORS API key), add it to `.env.example` with a placeholder in the same commit.

## Pitfalls from our earlier project

- The `.env` was once placed at the repo root with default permissions, exposing DB credentials to any local user. Always keep `chmod 600 .env`.
- Environment variables were referenced from the wrong path (`backend/` vs repo root). Keep a single `.env` at the repo root and document the expected path in the README.
