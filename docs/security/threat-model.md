# Threat Model / Risk List (I1)

**Project:** Shielding Crisis & Community Resilience — I1. **Scope:** FE↔BE API, external live sources, database, location data.

## 1. Attack surface

Attack surface (read top to bottom):

1. Users reach the app over HTTPS (JSON payloads), served by the Frontend (Vue).
2. Frontend (Vue) calls the Backend (FastAPI) via `/api/v1/...` (planned).
3. Backend (FastAPI) reads/writes:
   - Database (MySQL): household plans, test results
   - DS / spatial layer: BPA lookup, fire district lookup
   - External live sources: Vicmap Address, CFA FDR, BOM weather

Key properties to note:
- Backend has **no per-user application login** (decided for I1). Site access is gated by a **shared-password** Nginx basic auth layer so only the team and teaching staff can view the app; `household_id` is an unguessable capability token (128-bit random).
- `household_id` is user-supplied in URL paths — needs authorization checks (IDOR risk).
- Location data (address → lat/lng) is High-sensitivity PII.
- The app calls external services (Vicmap, CFA, BOM) — API keys and outbound-request behaviour matter.

## 2. Risk list

- **T1 — Unauthenticated access to household data** — Backend API — **Medium** (was High) — mitigated for I1: shared-password site gate (Nginx basic auth covering `/` and `/api`); no per-user login (decided 2026-08-31). Revisit if real accounts are added in I2
- **T2 — IDOR: access another household by ID** — `GET/PUT /api/v1/households/{id}` — **Medium** (was High) — mitigated: `household_id` is a random capability token (unguessable), and plan-save rejects cross-household references (`_validate_public_id_ownership`). Accepted for I1; revisit if the app adds accounts or sharing
- **T3 — SQL injection via input fields** — Backend / DB — **High** — parameterized queries / ORM only; never build SQL by string
- **T4 — XSS via user-entered names/roles** — Frontend — Medium — escape all output; validate input length/type
- **T5 — Location / PII exposure (breach or leak)** — Backend, logs, DB — **High** — minimisation (see privacy-requirements); no PII in logs; least-privilege DB user; restrict access
- **T6 — External API key leakage** — Backend, CI/CD, repo — **High** — secret-handling rules; secrets only in env / Actions secrets / Secrets Manager (see secret-handling)
- **T7 — External API abuse / slow downstream** — Backend — Medium — timeouts + sensible retry on Vicmap/CFA/BOM calls; handle failure gracefully
- **T8 — Error messages leak internals** — Backend — Medium — sanitized error responses; no stack traces in prod (FastAPI: debug off)
- **T9 — Oversized / malformed input** — Backend API — Medium — request size limits, length/type validation, basic rate-limit decision
- **T10 — DoS via unauthenticated endpoints** — Nginx / Backend — Medium — basic rate limiting at reverse proxy (deferred to deployment)

## 3. Highest-priority items for I1

1. **Auth model decided for I1** (2026-08-31): shared-password site gate (Nginx basic auth on `/` and `/api`), no per-user login; `household_id` is a capability token (T1, T2 mitigated for I1).
2. All DB access via **ORM/parameterized queries** (T3).
3. **No PII in logs or repo**, data minimisation enforced (T5).
4. **Secrets only in env / Actions secrets** (T6).
5. Timeouts on all external calls (T7).

## 4. Open questions

- **DECIDED (2026-08-31): no per-user login for I1.** Site access is gated by a shared password (Nginx basic auth on `/` and `/api`) so only the team and teaching staff can view the app. T1/T2 accepted with the mitigations above. Revisit in I2 if the app grows accounts.
- Which external API keys will I1 actually need? (Vicmap may not need a key; CFA/BOM feeds are keyless RSS.)

## 5. When to re-review

Re-run this model when: the API contract changes, or before first deployment. (The auth decision is now recorded above.)
