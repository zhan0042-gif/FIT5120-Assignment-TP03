# Threat Model / Risk List (I1–I2)

**Project:** Shielding Crisis & Community Resilience — I1–I2. **Scope:** FE↔BE API, external live sources (address, routing, AI), database, location data, and the CI/CD deploy path.
**Status:** T1–T10 retained from I1; T11–T13 added 2026-09-14 in the I2 review. Numbering is append-only — `deployment-checklist.md` and the vulnerability assessment report reference these IDs, so existing numbers are never re-used or re-ordered.

## 1. Attack surface

Attack surface (read top to bottom):

1. Users reach the app over HTTPS (JSON payloads), served by the Frontend (Vue).
2. Frontend (Vue) calls the Backend (FastAPI) via `/api/v1/...`.
3. Backend (FastAPI) reads/writes:

   - Database (MySQL): household plans, test results
   - DS / spatial layer: BPA lookup, fire district lookup, historical fire points
   - External live sources: TomTom Orbis Places (address lookup), TomTom Routing (travel time), CFA FDR, BOM weather
   - External AI provider: NVIDIA (`integrate.api.nvidia.com`) — rendezvous explanation (**new in I2**)
4. The CI/CD path also reaches production: GitHub Actions → AWS SSM → `scripts/deploy.sh` on the EC2 host.

Key properties to note:

- Backend has **no per-user application login** (decided for I1). Site access is gated by a **shared-password** Nginx basic auth layer so only the team and teaching staff can view the app; `household_id` is an unguessable capability token (128-bit random).
- `household_id` is user-supplied in URL paths — needs authorization checks (IDOR risk).
- Location data (address → lat/lng) is High-sensitivity PII.
- The app calls external services (TomTom Orbis, TomTom Routing, CFA, BOM, NVIDIA) — API keys and outbound-request behaviour matter.
- **Household data leaves our infrastructure in two I2 flows:** address text and coordinates → TomTom; a summary derived from household data → NVIDIA (see T13).

## 2. Risk list

| ID | Threat | Component | Severity | Control / status |
| -------- | --------------------------- | --------------- | ------------- | ------------------------------------- |
| T1 | Unauthenticated access to household data | Backend API | Medium (was High) | Shared-password site gate (Nginx basic auth on `/` and `/api`); no per-user login, decided 2026-08-31. Revisit if real accounts are added |
| T2 | IDOR: access another household by ID | `GET/PUT /api/v1/households/{id}` | Medium (was High) | `household_id` is a random capability token (unguessable), and plan-save rejects cross-household references (`_validate_public_id_ownership`) |
| T3 | SQL injection via input fields | Backend / DB | High | Parameterized queries / ORM only; never build SQL by string |
| T4 | XSS via user-entered names/roles | Frontend | Medium | Escape all output; validate input length and type |
| T5 | Location / PII exposure (breach or leak) | Backend, logs, DB | High | Minimisation (see privacy-requirements); no PII in logs; least-privilege DB user; restricted access |
| T6 | External API key leakage | Backend, CI/CD, repo | High | **Open** — see §2.1 |
| T7 | External API abuse / slow downstream | Backend | Medium | Bounded timeouts on TomTom / CFA / BOM calls; failure handled gracefully |
| T8 | Error messages leak internals | Backend | Medium | Sanitized error responses; no stack traces in prod (FastAPI: debug off) |
| T9 | Oversized / malformed input | Backend API | Medium | Request size limits; length and type validation |
| T10 | DoS via unauthenticated endpoints | Nginx / Backend | Medium | Basic rate limiting at the reverse proxy (deferred to deployment) |
| T11 | Silent deployment failure: stale code served as live | CI/CD path | High | Occurred 2026-09-08 to 2026-09-13; **fixed** — see §2.1 |
| T12 | Upstream request amplification | Backend → TomTom (paid) | Medium | **Open** — see §2.1 |
| T13 | Household data sent to a third-party AI provider | Backend → NVIDIA | Medium | **Open** — see §2.1 |

Severity is judged for our deployed context (a course prototype behind a shared-password gate), not for an open public service.

### 2.1 Detail on the open and narrative items

The table above is the index. These four carry a narrative that does not fit a table cell.

#### T6. External API key leakage

`backend/app/providers/tomtom.py` sends the key in a custom `TomTom-Api-Key` header while its client is created with `follow_redirects=True`. httpx strips only `Authorization` on a cross-origin redirect, so a 302 to a different host would replay the key. Fix = `follow_redirects=False` on keyed calls.

TomTom Routing passes the same key as a URL query parameter instead, following the provider's own API style — lower risk, because the request goes straight to TomTom over TLS and never through our reverse proxy, but it is a second pattern to keep in mind when adding a provider.

#### T11. Silent deployment failure: stale code served as live

Occurred 2026-09-08 to 2026-09-13. A force-push to `main` left the server's checkout diverged, so `git pull --ff-only` could never succeed again; `set -e` inside a function called as an `if` test hid the failure, so every deploy reported success while production ran five-day-old code.

Fixed 2026-09-13 (PR #45): the checkout is treated as disposable (`git fetch --prune` plus `git reset --hard origin/main`), the deploy body runs in a subshell so errexit applies, the kickoff runs under `set -e`, the deployed SHA is logged, and the script asserts `HEAD == origin/main` before reporting success.

Residual: deploy outcome is still a single status file, and a run in progress is indistinguishable from one that never started.

#### T12. Upstream request amplification

One plan-save request fans out into one paid verification call per entry: `services/plans.py` `_enrich_destination` calls `verify` unconditionally for the primary destination **and every backup arrangement**, `backup_arrangements` has no `max_items`, and `Destination.address` has no `max_length`. A single request can therefore drive an unbounded number of upstream calls (quota exhaustion, thread starvation).

Partly mitigated: `_enrich_members` short-circuits when a location is already verified.

Open: cap `backup_arrangements` and add a `max_length` to `Destination.address`.

#### T13. Household data sent to a third-party AI provider

The rendezvous explanation posts a summary derived from household data to a hosted model: each member's `display_name` and origin kind, plus the warning strings, which name a member's support needs. Privacy classifies support needs as High.

Controls in place: no address or coordinates are included; the response must survive gates (invented numbers, speculation about fire, gendered language, length and shape) or it is discarded unshown; a missing or invalid key disables the feature instead of failing the app.

Open: decide whether member names should be anonymised before sending, and whether the provider's retention terms are acceptable.

## 3. Highest-priority items

1. **Auth model decided for I1** (2026-08-31): shared-password site gate (Nginx basic auth on `/` and `/api`), no per-user login; `household_id` is a capability token (T1, T2 mitigated for I1).
2. All DB access via **ORM/parameterized queries** (T3).
3. **No PII in logs or repo**, data minimisation enforced (T5).
4. **Secrets only in env / Actions secrets** (T6).
5. Timeouts on all external calls (T7).
6. **Treat the deployment checkout as disposable and assert what actually deployed** (T11).
7. **Bound every input that fans out into paid upstream calls** (T12).
8. **Keep household data out of third-party AI calls wherever the model does not need it** (T13).

## 4. Open questions

- **DECIDED (2026-08-31): no per-user login for I1.** Site access is gated by a shared password (Nginx basic auth on `/` and `/api`) so only the team and teaching staff can view the app. T1/T2 accepted with the mitigations above. Revisit if the app grows accounts.
- **DECIDED (2026-09-10):** live address lookup requires `TOMTOM_API_KEY`, supplied to the Backend through its environment only. CFA/BOM feeds remain keyless.
- **DECIDED (2026-09-14):** the AI explanation provider is NVIDIA, keyed by `AI_API_KEY` (see secret-handling). The feature is optional by design — with no key the app still starts and the button simply produces nothing.
- **OPEN (2026-09-14):** whether the AI prompt should anonymise member names. The prompt currently sends `display_name` alongside a support-needs warning, which together identify a member's vulnerability. Recorded as T13.

## 5. When to re-review

Re-run this model when: the API contract changes, a new external data boundary is added, or the deployment path changes.

**Re-reviewed 2026-09-14 (I2).** Triggers met: the API contract gained the rendezvous simulation, rendezvous explanation, historical fire points, preparation support and PDF endpoints; NVIDIA became a new external data boundary; and the deploy path was rewritten after the 2026-09-08 incident. Result: T1–T10 retained, T11–T13 added.
