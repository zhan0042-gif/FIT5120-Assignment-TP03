# Threat Model / Risk List (I1–I3)

**Project:** Shielding Crisis & Community Resilience — I1–I3. **Scope:** FE↔BE API, external live sources (address, routing, road disruption, AI), database, location data, the archive environment, and the CI/CD deploy path.
**Status:** T1–T10 retained from I1; T11–T13 added 2026-09-14 in the I2 review; T14–T21 added in the I3 review; T22 added 2026-10-07, when the Safety Insights question box became a new external data boundary; T23 added 2026-10-12, when the voice assistant made OpenAI a second AI boundary. Numbering is append-only — `deployment-checklist.md` cites these IDs (the vulnerability assessment report uses its own F and R numbering instead), so existing numbers are never re-used or re-ordered.

## 1. Attack surface

Attack surface (read top to bottom):

1. Users reach the app over HTTPS (JSON payloads), served by the Frontend (Vue).
2. Frontend (Vue) calls the Backend (FastAPI) via `/api/v1/...`.
3. Backend (FastAPI) reads/writes:

   - Database (MySQL): household plans, test results
   - DS / spatial layer: BPA lookup, fire district lookup, historical fire points
   - External live sources: TomTom Orbis Places (address lookup), TomTom Routing (travel time), CFA FDR, BOM weather, the Victorian road disruption feed (DTP Open Data)
   - External AI provider: NVIDIA (`integrate.api.nvidia.com`) — rendezvous explanation (**new in I2**)
   - External AI provider: OpenAI (`api.openai.com`) — voice assistant: GPT-Live session creation and the Decisions action chooser (**new in I3**)

4. The CI/CD path also reaches production: GitHub Actions → AWS SSM → `scripts/deploy.sh` on the EC2 host.
5. The archive paths serve frozen iteration builds from `/i1/` and `/i2/` on the same nginx host, outside the application's routing tree.

Key properties to note:

- Backend has **no per-user application login** (decided for I1). Site access is gated by a **shared-password** Nginx basic auth layer so only the team and teaching staff can view the app; `household_id` is an unguessable capability token (128-bit random).
- `household_id` is user-supplied in URL paths — needs authorization checks (IDOR risk).
- Location data (address → lat/lng) is High-sensitivity PII.
- The app calls external services (TomTom Orbis, TomTom Routing, CFA, BOM, the Victorian road disruption feed, NVIDIA, OpenAI) — API keys and outbound-request behaviour matter.
- **Data leaves our infrastructure in four flows.** Two carry household records: address text and coordinates → TomTom, and a summary derived from household data → NVIDIA (see T13). The other two carry **user-authored content**: the question a household types into Safety Insights → NVIDIA (see T22), and what a household **says** to the voice assistant → OpenAI (see T23). The road disruption lookup is **not** a flow: it sends neither location nor address (see T18). The fire-danger prediction is not a flow either: it runs a model bundled with the backend, given only a district and a date.

## 2. Risk list

| ID | Threat | Component | Severity | Control / status |
| -------- | --------------------------- | --------------- | ------------- | ------------------------------------- |
| T1 | Unauthenticated access to household data | Backend API | Medium (was High) | Shared-password site gate (Nginx basic auth on `/` and `/api`); no per-user login, decided 2026-08-31. Revisit if real accounts are added |
| T2 | IDOR: access another household by ID | `GET/PUT /api/v1/households/{id}` | Medium (was High) | `household_id` is a random capability token (unguessable), and plan-save rejects cross-household references (`_validate_public_id_ownership`) |
| T3 | SQL injection via input fields | Backend / DB | High | Parameterized queries / ORM only; never build SQL by string |
| T4 | XSS via user-entered names/roles | Frontend | Medium | Escape all output; validate input length and type |
| T5 | Location / PII exposure (breach or leak) | Backend, logs, DB | High | Minimisation (see privacy-requirements); no PII in logs; restricted access. Not least-privilege today: `fit5120_app` holds `ALL PRIVILEGES` on the application database (vulnerability assessment report, F8; remediation R6 outstanding) |
| T6 | External API key leakage | Backend, CI/CD, repo | High | **Open** — see §2.1 |
| T7 | External API abuse / slow downstream | Backend | Medium | Bounded timeouts on TomTom / CFA / BOM / road disruption calls; failure handled gracefully |
| T8 | Error messages leak internals | Backend | Medium | Sanitized error responses; no stack traces in prod (FastAPI: debug off) |
| T9 | Oversized / malformed input | Backend API | Medium | Request size limits; length and type validation |
| T10 | DoS via unauthenticated endpoints | Nginx / Backend | Medium | Reverse-proxy rate limiting still deferred; of the two model-backed endpoints only the question endpoint is capped — see §2.1 |
| T11 | Silent deployment failure: stale code served as live | CI/CD path | High | Occurred 2026-09-08 to 2026-09-13; **fixed** — see §2.1 |
| T12 | Upstream request amplification | Backend → TomTom (paid) | Medium | **Open** — see §2.1 |
| T13 | Household data sent to a third-party AI provider | Backend → NVIDIA | Medium | **Open** — see §2.1 |
| T14 | Stale or inaccurate bushfire open data | Backend → spatial layer | Medium | Update schedule tracked in the data-management plan |
| T15 | False assurance | Frontend | Medium | Results presented as preparedness guidance, not a safety guarantee |
| T16 | Known-vulnerable dependencies | Backend / build | Medium | **Open** — see §2.1 |
| T17 | Service availability after host reboot or crash | EC2 / Docker | Medium | `restart: unless-stopped` on both services |
| T18 | Location disclosure to the external road disruption service | Backend → road disruption feed | Low (was High) | **Control verified** — see §2.1 |
| T19 | False assurance when road disruption data is unavailable | Backend → frontend | Medium | **Verified 2026-10-05** — see §2.1 |
| T20 | False completeness implied by a single prioritised recommendation | Frontend | Medium | **Open** — see §2.1 |
| T21 | Archived build path bypassing the site gate | Nginx / archive path | Medium | **Verified 2026-10-07** — see §2.1 |
| T22 | User-authored question text sent to a hosted model | Backend → NVIDIA | Medium | Controls in place, residual Medium — see §2.1 |
| T23 | Household speech sent to a third-party voice provider | Backend → OpenAI; browser → OpenAI | Medium | Controls in place, residual Medium — see §2.1 |

Severity is judged for our deployed context (a course prototype behind a shared-password gate), not for an open public service.

### 2.1 Detail on the open and narrative items

The table above is the index. These twelve carry a narrative that does not fit a table cell.

#### T10. DoS via unauthenticated endpoints

Reverse-proxy rate limiting is still deferred (`deployment-plan.md` §8), so the only rate limit on the deployed surface is the in-process `AskRateLimit` on the typed-question endpoint.

**Found 2026-10-05 (penetration test report, Test 11).** The two model-backed endpoints draw on one hosted quota — one `AI_API_KEY`, one account — but only `POST /api/v1/households/{id}/safety-guidance/ask` is capped. `POST /api/v1/households/{id}/rendezvous-explanation` carries no limit: eight sequential calls all reached the model. Household ids are free to create, so a caller behind the site gate can spend the shared quota through the uncapped endpoint and degrade both AI features for every other household.

The code comments overstate the position. `backend/app/services/rate_limit.py` and the I1 integration contract both describe the ask limit as protecting "the quota shared with the rendezvous explanation", which is true only in the direction that is capped.

Open: apply an equivalent limit to the explanation endpoint, and move the counters to a shared store if the deployment ever runs more than one worker (the counters are per process).

#### T6. External API key leakage

**Two** keyed clients send the key in a custom header while their httpx client is created with `follow_redirects=True`: `backend/app/providers/tomtom.py` (`TomTom-Api-Key`) and `backend/app/providers/road_disruptions.py` (`KeyID`, for the Victorian road disruption feed). httpx strips only `Authorization` on a cross-origin redirect, so a 302 to a different host would replay the key. Fix = `follow_redirects=False` on both keyed calls.

TomTom Routing passes the same key as a URL query parameter instead, following the provider's own API style — lower risk, because the request goes straight to TomTom over TLS and never through our reverse proxy, but it is a third pattern to keep in mind when adding a provider.

#### T11. Silent deployment failure: stale code served as live

Occurred 2026-09-08 to 2026-09-13. A force-push to `main` left the server's checkout diverged, so `git pull --ff-only` could never succeed again; `set -e` inside a function called as an `if` test hid the failure, so every deploy reported success while production ran five-day-old code.

Fixed 2026-09-13 (PR #45): the checkout is treated as disposable (`git fetch --prune` plus `git reset --hard origin/main`), the deploy body runs in a subshell so errexit applies, the kickoff runs under `set -e`, the deployed SHA is logged, and the script asserts `HEAD == origin/main` before reporting success.

Residual: deploy outcome is still a single status file, and a run in progress is indistinguishable from one that never started.

#### T12. Upstream request amplification

One plan-save request fans out into one paid verification call per entry: `services/plans.py` `_enrich_destination` calls `verify` unconditionally for the primary destination **and every backup arrangement**, `backup_arrangements` has no `max_items`, and `Destination.address` has no `max_length`. A single request can therefore drive an unbounded number of upstream calls (quota exhaustion, thread starvation).

Measured against production 2026-10-05 (penetration test report, Test 7): a plan with 100 backup arrangements took 34.88 s against 5.17 s for 10, about 0.33 s per entry on top of roughly 1.9 s of fixed overhead, and still returned 200. At that rate the reverse proxy's 60 s timeout is reached at approximately 176 entries. The impact is bounded to latency and external API cost.

Partly mitigated: `_enrich_member_locations` short-circuits when a location is already verified.

Open: cap `backup_arrangements` and add a `max_length` to `Destination.address`.

#### T13. Household data sent to a third-party AI provider

The rendezvous explanation posts a summary derived from household data to a hosted model: each member's `display_name`, origin kind and travel time in minutes, the household's total time to be together, plus the warning strings, which name a member's support needs. Privacy classifies support needs as High.

Controls in place: no address or coordinates are included; the response must survive gates (invented numbers, speculation about fire, gendered language, length and shape) or it is discarded unshown; a missing or invalid key disables the feature instead of failing the app.

Open: decide whether member names should be anonymised before sending, and whether the provider's retention terms are acceptable.

#### T16. Known-vulnerable dependencies

The vulnerability assessment identified geopandas 1.1.1 (HIGH) and six advisories against starlette 0.47.3 via fastapi 0.116.1; the pytest pin has since moved from 8.4.1 to 9.0.3.

**The geopandas finding no longer applies to production.** geopandas and pyarrow were moved out of the backend into `data/requirements.txt` on 2026-09-10, so they are not installed in the deployed image at all, and the pin has since moved from 1.1.1 to 1.1.2 (`dependency-scan.md`, re-checked 2026-09-14). The live finding on this boundary is `starlette`, which still arrives transitively through `fastapi` — precisely the transitive check Dependabot does not perform.

None is currently reachable through the deployed surface, but the pinned versions are the fastest-moving part of the stack. Open: raise the pins and add `pip-audit` to CI so this is detected rather than re-discovered.

**Updated 2026-10-15.** Dependabot reports **1 critical and 1 high** on `main`, both in `frontend/package-lock.json`, but they do not share a reachability story. `maplibre-gl` (sanitizer bypass in `DOM.sanitize()`, installed 5.24.0, patched in 6.4.1) is a runtime dependency: it is bundled and does ship to visitors, and the fix is a major-version upgrade. `source-map-js` (event-loop denial of service, installed 1.2.1, patched in 1.2.2) is build-time only — it arrives through `@vue/compiler-sfc` and `postcss`, is imported by no runtime code, and never enters the browser bundle, so its denial of service lands on the build machine and on CI rather than on a visitor. Both are dispositioned as documented exceptions, with a written reachability assessment in `dependency-scan.md`.

#### T18. Location disclosure to the external road disruption service

This entry previously asserted that the disruption lookup sent evacuation destination coordinates to the external feed, and rated that High. Reading the provider shows it does not.

`backend/app/providers/road_disruptions.py` `_fetch_all()` requests the public feed with pagination only (`page`, `limit`) and the key in a `KeyID` header. The destination coordinates are passed into `_parse_record` and used **locally** to compute distance and discard records beyond the radius (`distance_km > radius_km`). **No location, no address and no household identifier leaves our infrastructure for this feature.** The outbound request contains no household-derived field at all.

Recorded at length because the earlier draft of this model and the Security Plan both asserted the opposite, and because the Privacy Requirements docstrings and the code agree with this version.

Severity lowered from High to Low. The residual concern on this boundary is not the coordinates but the **key**: it travels in a header on a client created with `follow_redirects=True`, which is the T6 pattern. Fixing T6 fixes this too.

#### T19. False assurance when road disruption data is unavailable

If the feed cannot be reached, presenting a successful "no disruptions" result would convert a data-availability failure into apparent reassurance about a route. Controls in place: "no disruptions found" and "information unavailable" are distinct states end to end, and the unavailable state carries no disruption details, distances or impact information.

Verified 2026-10-05 (penetration test report): an evacuation destination without verified coordinates returns the "cannot be checked" state rather than issuing a lookup, and when the feed is unavailable the interface states that information is unavailable rather than presenting zero disruptions.

#### T20. False completeness implied by a single prioritised recommendation

Presenting one priority issue and one next action may be read as a completeness statement about the household's preparedness rather than a ranking of known issues.

**Open.** The control previously recorded here was that the interface states the result ranks known issues and is not a completeness assessment. **No such statement exists in the code.** Searching the frontend and the backend for that wording returns nothing, and `prepSupport` in `frontend/src/stores/localContext.js` is fetched and exposed by the store but read by no component. The preparation status card that would have presented the recommendation, `frontend/src/components/localContext/PreparationSupportBanner.vue`, was removed from the overview in `65ed2f6` on 2026-10-07, so the risk is not currently exposed in the interface.

Residual: the disclaimer the control depends on is absent rather than merely removed. If preparation guidance is surfaced again, the interface must state that the result ranks known issues and is not a completeness assessment.

#### T21. Archived build path bypassing the site gate

Serving archived iteration builds from `/i1/` (Iteration 1) and `/i2/` (Iteration 2) on the same host adds served paths outside the application's routing tree. The concern is a path that answers without the gate.

The earlier draft recorded that "Nginx applies `auth_basic` per location block, so a new location does not inherit the gate unless it is set explicitly". **That is not how this host is configured.** `auth_basic` and `auth_basic_user_file` sit at **server** level in `/etc/nginx/sites-enabled/default`, and nginx location blocks **inherit server-level directives**. The archive blocks therefore carry the gate without repeating it. Adding `auth_basic` inside `location /i1/` would be redundant, and its absence there is not a gap.

Control in place: both archive paths inherit the server-level gate, and each carries its own `try_files` so a deep link such as `/i1/plan` resolves inside the archive rather than falling through to the main site's `index.html`.

Residual: the gate is a **single shared password for everything**, so the archive is exactly as protected as the application and no better.

**Verified 2026-10-07.** The probe was run against production without credentials: `https://cubesix.me/`, `https://cubesix.me/i1/` and `https://cubesix.me/i2/` each returned `401`. The gate is inherited as described and both archive paths are covered. The penetration test report's Test 2 asserts the gate for all traffic but names neither archive path, so the per-path result is recorded here rather than left to that report.

#### T22. User-authored question text sent to a hosted model

The Safety Insights question box (`POST /api/v1/households/{household_id}/safety-guidance/ask`) sends what the household typed to a hosted model (`nvidia/nemotron-3-super-120b-a12b`, the same NVIDIA chat endpoint the explanation uses). When it was recorded this was the only outbound boundary whose payload is **written by a user**; T23's action chooser acquired the same property on 2026-10-12. Unlike every other boundary, then, its content cannot be described by a field list: a household can type a name, an address or a medical detail into it.

What is sent: the typed question, plus **our own** reviewed answer catalogue (each entry's id, question and alternative phrasings). What is not sent: `household_id`, the saved plan, and every address and coordinate the plan holds. The question is not attached to any household record — as the endpoint's own docstring puts it, "the household id only scopes the route".

Controls in place (`backend/app/providers/nvidia_guidance_router.py`, `backend/app/services/safety_guidance_ask.py`):

- **The model's output is never shown and never stored.** It returns ids; every id is checked against the reviewed catalogue before use, and the browser renders the reviewed entry instead. A confused, jailbroken or swapped model cannot place its own text in front of a household.
- **The question cannot escape its delimiters.** `<` and `>` are replaced before the prompt is built, so the typed text cannot close the `<question>` block, and the system prompt states the block is untrusted and any instruction inside it must be ignored. Instruction-override attempts are part of the router evaluation set (`docs/design/safety-qa-router-evaluation.md`).
- **Emergency wording is answered before the model is called**, by a deterministic check, so a distress message is never sent to a provider and never waits on one.
- **The question is length-capped** at 300 characters (`MAX_QUESTION_LENGTH`), because the field is sent to a hosted model.
- **The question is never logged.** A rejection records the reason, not the text.
- **The endpoint is rate-limited** (`AskRateLimit`: 6 per household, 30 overall, per 60-second window), which bounds how much user text can be pushed to the provider in a burst.

Residual: Medium. The payload is user-authored and therefore unbounded in *content* even though it is bounded in length, and it leaves our infrastructure to a third party under that provider's terms. The compensating controls are strong on the output side — nothing the model produces reaches a user — but they do not change the fact that the typed text is transmitted.

Open: whether the provider's retention terms are acceptable for user-authored text, and whether the question should be screened for address-like content before it is sent.

#### T23. Household speech sent to a third-party voice provider

The voice assistant (added 2026-10-08) is the only feature that sends **spoken** household input to a third party, and it does so in two different shapes — both to OpenAI.

**The session handshake carries no household data.** `backend/app/providers/openai_live.py` posts to `POST https://api.openai.com/v1/live/sessions` (model `gpt-live-1`) and returns the SDP answer. The body is the model name, our fixed instructions, `delegation: {type: "client"}` and the browser's **WebRTC offer** — a transport descriptor, not a household field. Nothing about the household is attached; `household_id` scopes the route and the rate limit only.

**The audio does not pass through us.** The session is created with client delegation, so the browser holds the media session itself and the person's live microphone audio flows from the browser to OpenAI without transiting our backend. *Inferred* from the WebRTC plus client-delegation shape of the handshake rather than measured; confirm by watching the browser's network tab for a direct connection to `api.openai.com` during a session. The consequence is what matters: this is the one household input to a third party that we cannot inspect, minimise, filter or log.

**The action chooser sends the spoken request.** `backend/app/providers/openai_decisions.py` posts to `POST https://api.openai.com/v1/decisions` (model `gpt-6-luna`). The payload is built by `services/voice_actions.py` `decision_input()` and contains three things: the last request the person made (capped at 300 characters), the name of the page they are on, and the text last read out to them (each capped at 40). It carries **no household record** — not the plan, not an address, not a coordinate — and the utterance is never logged.

Controls in place (`backend/app/api/routes/live.py`, both providers, `services/voice_actions.py`):

- **The model chooses from a closed list and nothing else.** It returns `choice` values for two named questions — an action and an emotion — and anything outside the list, or below `MIN_CONFIDENCE`, becomes `none`. No text the model writes is shown to a user or stored.
- **The model is told not to speak from its own knowledge.** `LIVE_INSTRUCTIONS` requires it to delegate every safety, weather, fire-danger, plan and navigation question to the backend and never to read out or invent a figure; spoken figures are templated by code from store values.
- **Emergency wording is handled before the provider is reached**, by a deterministic check, so a distress message is answered by our own route rather than carried to a voice model.
- **Both endpoints are rate-limited** — `POST /live/sessions` and `POST /live/decide` each take an `AskRateLimit`.
- **Nothing is logged.** Neither the WebRTC offer nor the utterance is written to a log; both route docstrings state this.

Residual: Medium. The chooser has the same property as T22 — the payload is written by the person speaking, so its content cannot be bounded by a field list even though its length is capped. The audio is a different order of thing: a voice recording carries identity that typed text does not (tone, accent, background sound), it reaches the provider directly rather than through our backend, and our controls cannot touch it. `OPENAI_API_KEY` is also held on a **different account** from every other key in this project — the AI developer's OpenAI account, not the deployment lead's (see `secret-handling.md`) — so the provider relationship is not the deployment lead's to review on the same terms as the others.

Open: whether OpenAI's retention terms are acceptable for household speech, and whether the voice feature should be opt-in per household rather than present for everyone behind the gate.

## 3. Highest-priority items

1. **Auth model decided for I1** (2026-08-31): shared-password site gate (Nginx basic auth on `/` and `/api`), no per-user login; `household_id` is a capability token (T1, T2 mitigated for I1).
2. All DB access via **ORM/parameterized queries** (T3).
3. **No PII in logs or repo**, data minimisation enforced (T5).
4. **Secrets only in env / Actions secrets** (T6).
5. Timeouts on all external calls (T7).
6. **Treat the deployment checkout as disposable and assert what actually deployed** (T11).
7. **Bound every input that fans out into paid upstream calls** (T12).
8. **Keep household data out of third-party AI calls wherever the model does not need it** (T13), and **never render model output as guidance** — the safety question box asks the model for reviewed-answer ids only, and every word a user reads comes from the reviewed catalogue (T22).
9. **Send external services the minimum they need** — the road disruption lookup sends no household field at all, which is the standard the other boundaries are measured against (T18).
10. **Cap every endpoint that spends a shared quota.** Both model-backed endpoints draw on one hosted key; a limit on one of them bounds nothing while the other is open (T10).
11. **Treat voice as a boundary of its own, not as "just another API call"** (T23). The chooser can be minimised the way any payload can — it sends the spoken request and two labels, and the model returns a closed-list choice. The audio cannot: it goes from the browser to the provider without passing through us. Decide deliberately whether that is acceptable, because it is the one flow where our own controls stop applying.

## 4. Open questions

- **DECIDED (2026-08-31): no per-user login for I1.** Site access is gated by a shared password (Nginx basic auth on `/` and `/api`) so only the team and teaching staff can view the app. T1/T2 accepted with the mitigations above. Revisit if the app grows accounts.
- **DECIDED (2026-09-10):** live address lookup requires `TOMTOM_API_KEY`, supplied to the Backend through its environment only. CFA/BOM feeds remain keyless.
- **DECIDED (2026-09-14):** the AI explanation provider is NVIDIA, keyed by `AI_API_KEY` (see secret-handling). The feature is optional by design — with no key the app still starts and the button simply produces nothing.
- **DECIDED (2026-10-01):** live road disruption data requires `VIC_ROAD_DISRUPTIONS_API_KEY`, supplied to the Backend through its environment only. With no key the provider is replaced by a disabled client, so the app starts normally and that feature reports "information unavailable" (T19).
- **DECIDED (2026-10-05):** the Safety Insights question box routes through a hosted model that returns **reviewed-answer ids only**; the model's own text is never shown to a user or stored. Selected by the evaluation recorded in `docs/design/safety-qa-router-evaluation.md` (see T22).
- **DECIDED (2026-10-08):** the voice assistant uses OpenAI (`OPENAI_API_KEY`) with client delegation. The session handshake carries only the WebRTC offer and our fixed instructions; the action chooser sends the spoken request, the current page and the last readout, and nothing about the household. Both endpoints are rate-limited and neither the offer nor the utterance is logged (T23).
- **OPEN (2026-09-14):** whether the AI prompt should anonymise member names. The prompt currently sends `display_name` alongside a support-needs warning, which together identify a member's vulnerability. Recorded as T13.
- **OPEN (2026-10-07):** whether the provider's retention terms are acceptable for the user-authored question text the Safety Insights box transmits, and whether that text should be screened for address-like content before it is sent. Recorded as T22.
- **OPEN (2026-10-05):** apply the `AskRateLimit` pattern to the rendezvous explanation endpoint, which currently has no limit while drawing on the same hosted quota as the capped question endpoint. Recorded as T10.
- **OPEN (2026-10-12):** whether OpenAI's retention terms are acceptable for household speech, which is the one input we cannot inspect before it reaches the provider, and whether the voice feature should be opt-in per household. Recorded as T23.

## 5. When to re-review

Re-run this model when: the API contract changes, a new external data boundary is added, or the deployment path changes.

**Re-reviewed 2026-09-14 (I2).** Triggers met: the API contract gained the rendezvous simulation, rendezvous explanation, historical fire points, preparation support and PDF endpoints; NVIDIA became a new external data boundary; and the deploy path was rewritten after the 2026-09-08 incident. Result: T1–T10 retained, T11–T13 added.

**Re-reviewed 2026-09 (I3).** Triggers met: the API contract gained the road disruption and prioritisation features; the Victorian road disruption feed became a new external data boundary; and the archive environment added served paths outside the application routing tree. Result: T1–T13 retained, T14–T21 added.

**Re-reviewed 2026-10-07 (I3).** Trigger met: a new external data boundary — the Safety Insights question box transmits user-authored text to a hosted model, which is a different shape from the household-derived summary T13 already covered. Result: T1–T21 retained, **T22 added**. Same review: the T21 archive probe was run against production and `/`, `/i1/` and `/i2/` each return `401`; the control is recorded as verified rather than in place.

**Recorded 2026-10-07 (I3).** The 2026-10-05 penetration test report (Test 11) found that two model-backed endpoints draw on one hosted quota and only one of them is rate-limited. The finding is recorded under **T10**, which had read "rate limiting at the reverse proxy (deferred to deployment)" since I1 and had not been updated when a partial limit was added to a single endpoint.

**Re-reviewed 2026-10-12 (I3).** Trigger met: a new external data boundary — the voice assistant sends household speech to OpenAI, in two shapes that behave differently (an SDP-only session handshake through our backend, and live audio from the browser that never passes through us). Result: T1–T22 retained, **T23 added**.

**Corrected 2026-10-06 (I3).** Two entries in the I3 addition were wrong on the facts and are corrected above rather than renumbered, because the IDs are referenced elsewhere:

- **T18** claimed destination coordinates were transmitted to the road disruption feed and was rated High. The provider sends no household-derived field at all. Severity lowered to Low and the control recorded as verified (see §2.1).
- **T21** stated that nginx does not inherit `auth_basic` into a new location block. On this host the directive is set at server level and **is** inherited, so the archive paths were never ungated. The premise is corrected and the control recorded as in place (see §2.1).
