# Security & Privacy Requirements (I1–I2)

**Project:** Shielding Crisis & Community Resilience (SDG 1 & 2) — I1 "Build & Check My Preparedness" and I2 (rendezvous simulation, AI explanation, fire map).
**Owner:** Cybersecurity & Deployment Lead. **Status:** I1–I2, updated 2026-09-14 after the I2 API contract change.

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
- Voice transcripts and spoken values, except in the local voice turn log with `VOICE_LOG_CONTENT=true`. The application logger and error messages never carry them. `logs/` is gitignored.

## 5. External data boundaries

| Service | Data sent | Sensitivity |
| ------------------------- | -------------------------------------------------- | ------------------------- |
| TomTom Orbis Places API | Address text and coordinates, for suggestion, geocoding and reverse geocoding | High (coordinates) — keep server-side |
| TomTom Routing API | Origin and destination coordinates for travel-time estimation; no address text | High (coordinates) |
| CFA Fire Danger Rating feed | Fire danger rating by district | Low |
| BOM weather feed | Weather context | Low |
| BPA / Fire District open data (DS layer) | Spatial lookup | Low |
| NVIDIA hosted model API (`integrate.api.nvidia.com`) | A summary derived from the household's plan — see the note below | High in combination |
| Browser speech recognition (Chrome / Edge Web Speech API) | The audio of what the user says while voice control is on | High — may include names and addresses; sent by the browser to Google, not by our backend |
| Voice judge (`/voice/judge`; mock locally, JEV once connected) | The transcript, the current page's field labels and current values (member names, typed addresses) | High in combination |

**Note on the NVIDIA boundary.** Data sent: each member's display_name, origin kind (home / work / school / other), travel and waiting minutes, and the plan's own warning strings. **No address text and no coordinates are sent.** A member's name together with a support-needs warning identifies an individual's vulnerability, so this boundary carries High-sensitivity data in combination; it is tracked as T13 in the threat model, and anonymising the name before sending remains an open decision.

Rule: external live data is never merged with or stored alongside household PII without a clear purpose.

**Deliberate exception:** the rendezvous explanation sends the summary above to NVIDIA for the sole purpose of producing the user-requested explanation text. There is no other purpose, no data is retained on our side, and the response is discarded if it fails the gates. Any new field added to that payload must be justified here first.

**Note on voice control.** Voice control is off until the user presses the
microphone button, and a session ends on "stop", on the button, or after 30
seconds of silence. The mock judge runs inside our backend; nothing leaves the
machine except the browser's own audio stream to its speech service. Before JEV
is connected, the payload it receives must be reviewed here, as for NVIDIA.

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
