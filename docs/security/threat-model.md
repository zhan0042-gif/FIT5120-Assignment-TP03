# Threat Model / Risk List (I1)

**Project:** Shielding Crisis & Community Resilience — I1. **Scope:** FE↔BE API, external live sources, database, location data.

## 1. Attack surface

```
 User
  │  JSON over HTTPS
  v
Frontend (Vue)
  │  /api/v1/...  (planned)
  v
Backend (FastAPI)
  ├──► Database (MySQL)            household plans, test results
  ├──► DS / spatial layer          BPA lookup, fire district lookup
  └──► External live sources       Vicmap Address, CFA FDR, BOM weather
```

Key properties to note:
- Backend currently has **no application-level auth** (relies on Nginx basic auth / future auth layer).
- `household_id` is user-supplied in URL paths — needs authorization checks (IDOR risk).
- Location data (address → lat/lng) is High-sensitivity PII.
- The app calls external services (Vicmap, CFA, BOM) — API keys and outbound-request behaviour matter.

## 2. Risk list

- **T1 — Unauthenticated access to household data** — Backend API — **High** — auth layer / Nginx basic auth over HTTPS; document auth model before deploy
- **T2 — IDOR: access another household by ID** — `GET/PUT /api/v1/households/{id}` — **High** — **DECIDED (I1): no app-level login, so no per-user ownership check. Risk accepted for prototype/demo; add ownership checks if multi-user data is introduced later.**
- **T3 — SQL injection via input fields** — Backend / DB — **High** — parameterized queries / ORM only; never build SQL by string
- **T4 — XSS via user-entered names/roles** — Frontend — Medium — escape all output; validate input length/type
- **T5 — Location / PII exposure (breach or leak)** — Backend, logs, DB — **High** — minimisation (see privacy-requirements); no PII in logs; least-privilege DB user; restrict access
- **T6 — External API key leakage** — Backend, CI/CD, repo — **High** — secret-handling rules; secrets only in env / Actions secrets / Secrets Manager (see secret-handling)
- **T7 — External API abuse / slow downstream** — Backend — Medium — timeouts + sensible retry on Vicmap/CFA/BOM calls; handle failure gracefully
- **T8 — Error messages leak internals** — Backend — Medium — sanitized error responses; no stack traces in prod (FastAPI: debug off)
- **T9 — Oversized / malformed input** — Backend API — Medium — request size limits, length/type validation, basic rate-limit decision
- **T10 — DoS via unauthenticated endpoints** — Nginx / Backend — Medium — basic rate limiting at reverse proxy (deferred to deployment)

## 3. Highest-priority items for I1

1. Define the **auth model** before anything real is deployed (T1, T2).
2. All DB access via **ORM/parameterized queries** (T3).
3. **No PII in logs or repo**, data minimisation enforced (T5).
4. **Secrets only in env / Actions secrets** (T6).
5. Timeouts on all external calls (T7).

## 4. Open questions

- ~~Is backend application-level auth in scope for I1?~~ **DECIDED: no application-level login for I1** — Nginx basic auth only; T2 accepted for the demo.
- Which external API keys will I1 actually need? (Vicmap may not need a key; CFA/BOM feeds are keyless RSS.)

## 5. When to re-review

Re-run this model when: the API contract freezes, auth is decided, or before first deployment.
