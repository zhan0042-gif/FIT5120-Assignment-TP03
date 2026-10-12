# Security & Privacy Requirements (I1–I3)

**Project:** Shielding Crisis & Community Resilience (SDG 1 & 2) — I1 "Build & Check My Preparedness", I2 (rendezvous simulation, AI explanation, fire map) and I3 (travel disruption awareness, personalised preparedness prioritisation).
**Owner:** Cybersecurity & Deployment Lead. **Status:** I1–I3, updated 2026-10-06 after the I3 API contract change.

## 1. Purpose

Define what data the app collects, how sensitive each piece is, and the handling rules for the whole team. This is the basis for the threat model and the deployment checklist.

## 2. Data classification

The app handles household preparedness data. Combined, these fields can reveal a household's identity and home location, so even for a student prototype we follow **collect-the-minimum** and **never log or commit real data**.

| Field | Source | Sensitivity | Handling rule |
| ---------------------- | -------------------- | ----------- | ----------------------------------------------- |
| Household display_name | Frontend form | Low | Prefer display_name / household role; never collect full real names if a display name suffices |
| Member support needs / mobility notes | Frontend form | High | Never in logs, never in the public repo, never in mock or seed data |
| Pets | Frontend form | Low–Med | No rule beyond the minimisation principles in §3 |
| Home location / address | Frontend form (PUT location) | High | PII + geolocation; resolved lat/lng stored server-side only; never in logs or error messages |
| Device-shared coordinates | Browser geolocation on an explicit user gesture (PUT location/device) | High | Sent once and stored like a home location; never presented as a verified postal address — see the note below |
| Primary / backup destinations | Frontend form | Med–High | Reveals regular movement patterns |
| Member usual location (work / school / other address) | Frontend form (PUT plan) | High | PII + geolocation, same handling as home address. User-declared *hypothetical* locations used for simulation only; optional, and the rest of the plan works without them |
| Responsibilities / household arrangements | Frontend form | Med | Who does what in a household |
| Rendezvous simulation result | Derived server-side from the plan above | Med–High | Reveals where each member is and when they would arrive at the evacuation destination. Derived data inherits the sensitivity of its inputs: never in logs, never in the repo |
| Written plan (PDF export) | Generated from the plan | High | Aggregates home address, destinations, member names and support needs into one document; generated on request and never stored server-side |
| Road disruption lookup result | Derived server-side from the plan's destinations | Low | Public road disruption data filtered to a radius around a destination. Reveals a destination only inside our own infrastructure — nothing about the household is sent outbound (see §5) |

**Note on device-shared coordinates.** Collected only after the user presses the button and grants permission, and the user can always type an address instead. This is **not** continuous tracking: there is no background or periodic position reporting, and no history of positions is kept.

## 3. Minimisation principles

1. **Only collect what a feature needs.** The API contract asks for display_name and household role — do not add fields like date of birth, phone numbers, or national IDs without a feature requirement.
2. **Prefer display_name / household role over real identity.** Real full names and other identifying data are out of scope.
3. **No real test data in the repo.** Seed data, mock data, and examples must be obviously fake (e.g. "Alice", "123 Fake Street").
4. **No PII in logs.** The backend must not log addresses, coordinates, or support needs. Log request IDs and non-sensitive status only.
5. **Send a third party the minimum it needs to do its job.** Where a feature depends on an external service, send the smallest payload that produces the result — and never send identifiers the service does not use.

## 4. What must not appear in the repository or logs

- Real addresses or coordinates of anyone.
- Support needs / mobility notes of real people.
- Database passwords or API keys (see secret-handling).
- Any data that, combined, identifies a real household.
- Generated AI passages that failed their safety gates — rejected text is discarded, not logged (it can quote household data).

## 5. External data boundaries

| Service | Data sent | Sensitivity |
| ------------------------- | -------------------------------------------------- | ------------------------- |
| TomTom Orbis Places API | Address text and coordinates, for suggestion, geocoding and reverse geocoding | High (coordinates) — keep server-side |
| TomTom Routing API | Origin and destination coordinates for travel-time estimation; no address text | High (coordinates) |
| CFA Fire Danger Rating feed | Fire danger rating by district | Low |
| BOM weather feed | Weather context | Low |
| BPA / Fire District open data (DS layer) | Spatial lookup | Low |
| Victorian road disruption feed (DTP Open Data) | **Nothing about the household** — pagination only (`page`, `limit`) plus the key in a `KeyID` header | None — see the note below |
| NVIDIA hosted model API (`integrate.api.nvidia.com`) — rendezvous explanation | A summary derived from the household's plan — see the note below | High in combination |
| NVIDIA hosted model API (`integrate.api.nvidia.com`) — safety question routing | The user's typed question, plus our own reviewed answer catalogue — see the note below | **Unbounded** — user-authored free text |

**Note on the NVIDIA explanation boundary.** Data sent: each member's display_name, origin kind (home / work / school / other), travel and waiting minutes, and the plan's own warning strings. **No address text and no coordinates are sent.** A member's name together with a support-needs warning identifies an individual's vulnerability, so this boundary carries High-sensitivity data in combination; it is tracked as T13 in the threat model, and anonymising the name before sending remains an open decision.

**Note on the NVIDIA question-routing boundary.** This is the only boundary whose payload is written by a user, so its sensitivity cannot be bounded in advance: a household can type anything into the question box, including a name or an address. What is sent is the typed question together with **our own** reviewed answer catalogue (each entry's id, question and alternative phrasings); **no household record is attached** — not `household_id`, not the saved plan, not any address or coordinate the plan holds. Controls on the boundary, all in `backend/app/providers/nvidia_guidance_router.py` and `backend/app/services/safety_guidance_ask.py`:

- **The model returns ids and nothing else.** Every id is checked against the reviewed catalogue before use, and no text the model writes is ever shown to a user or stored. A model that is jailbroken, confused or replaced cannot put words in front of a household.
- **The question cannot escape its delimiters.** `<` and `>` are replaced before the prompt is built, so the typed text cannot close the `<question>` block, and the system prompt states that the block is untrusted and any instruction inside it must be ignored.
- **The question is length-capped** at 300 characters (`MAX_QUESTION_LENGTH`), so a household cannot paste a document into a field that is transmitted to a provider.
- **Emergency wording never reaches the model.** It is recognised deterministically first, so a distress message is answered by our own route rather than routed.
- **The question is never logged.** A rejection message names the reason, not the text.
- **The endpoint is rate-limited** (`AskRateLimit`), which bounds how much user text can be pushed to the provider per window.

This boundary is tracked as T22 in the threat model. It is recorded here because a boundary whose payload the user controls is the one place a privacy review cannot reason from a fixed field list.

**Note on the road disruption boundary.** This is the one external boundary that receives **no household data at all**. `backend/app/providers/road_disruptions.py` fetches the public feed page by page (a `page` and a `limit` parameter, nothing more) and filters it **locally**: each record's coordinates are compared against the destination and dropped when the distance exceeds the configured radius. Destination coordinates therefore never leave our infrastructure for this feature, and no address text or household identifier is involved.

An earlier draft of the threat model and of the Security Plan stated the opposite, that destination coordinates were transmitted to this service. The code does not do that; the error is corrected in the threat model (T18). It is recorded here because "what we do not send" is the part of a boundary that is easiest to get wrong and hardest to notice.

This boundary is the standard the others are measured against under §3 rule 5: an external service receives the smallest payload that produces the result, and never an identifier it does not use.

Rule: external live data is never merged with or stored alongside household PII without a clear purpose.

**Deliberate exceptions:** two flows send data to NVIDIA, and both do so for the sole purpose of producing the response the household asked for. The rendezvous explanation sends the plan summary; the safety question box sends the typed question. Neither has a second purpose, neither retains anything on our side, and a response that fails its gate is discarded rather than stored or shown. Both are listed above so that the exception is a recorded decision rather than an omission — and any new field added to either payload must be justified here first.

## 6. Requirements for the team

- **Frontend:** escape all user-entered values before display (XSS); never bundle secrets in the build; don't send fields the contract doesn't define. Request browser geolocation **only** on an explicit user gesture, never on page load, and always offer the typed-address alternative.
- **Backend:** validate input length/type on every endpoint; never echo raw input back into errors; external API calls need timeouts; parameterized queries / ORM only (no string-built SQL). Never log request bodies, addresses or coordinates.
- **Database:** least-privilege app account (see `MYSQL_USER` in secret-handling); no passwords in repo; separate fake test data from real data.
- **DS:** respect open-data licences/attribution; processed open data must not be mixed with real household data.
- **Anyone adding an external service:** add the boundary to §5 in the same PR that introduces the call.

## 7. Review checklist

- [ ] Fields in the API contract match this classification.
- [ ] Frontend collects no fields outside the contract.
- [ ] Backend logs contain no addresses / coordinates / support needs.
- [ ] No real personal data in mock or seed data.
- [ ] `.env.example` has no real secrets.
- [ ] Every outbound service call appears in §5 with the data it receives.
